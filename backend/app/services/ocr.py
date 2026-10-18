from io import BytesIO
import logging
import re
import time

from google.api_core.exceptions import GoogleAPIError, InternalServerError
from google.cloud import documentai_v1 as documentai
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ContentStream

from app.core.config import get_settings
from app.core.gcp import docai, docai_processor_name

# OCR fallback stays small; native-text pages need no Document AI request.
PAGES_PER_REQUEST = 5
log = logging.getLogger(__name__)


class PdfTooLongError(ValueError):
    pass


class OcrProcessingError(GoogleAPIError):
    def __init__(self, cause, start, end):
        super().__init__('The PDF reading service could not complete this page group.')
        self.code = int(cause.code)
        self.page_start, self.page_end = start, end


def _pdf_bytes(pages):
    writer = PdfWriter()
    for page in pages:
        writer.add_page(page)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _reader(pdf_bytes):
    reader = PdfReader(BytesIO(pdf_bytes))
    total = len(reader.pages)
    limit = get_settings().max_policy_pages
    if total > limit:
        raise PdfTooLongError(f'PDF has {total} pages; the limit is {limit}.')
    return reader


def _split_pdf(pdf_bytes: bytes):
    reader = _reader(pdf_bytes)
    for start in range(0, len(reader.pages), PAGES_PER_REQUEST):
        yield start, _pdf_bytes(reader.pages[start:start + PAGES_PER_REQUEST])


def _page_text(document: documentai.Document, page: documentai.Document.Page) -> str:
    return ''.join(document.text[seg.start_index:seg.end_index]
                   for seg in page.layout.text_anchor.text_segments).strip()


def _native_text(page):
    """Conservative heuristic: substantial images and doubtful text use OCR.

    Inspect drawn content (including nested Forms), not shared resource tables.
    Only small header/footer images alongside a strong text layer are allowed.
    This is a quality gate, not proof that a PDF text layer is correct.
    """
    try:
        if page.get('/Annots') or page.rotation:
            return None
        bounds = page.mediabox
        width, height = float(bounds.width), float(bounds.height)
        if width <= 0 or height <= 0:
            return None
        image_area = 0
        images = 0

        def multiply(m, n):
            a, b, c, d, e, f = m
            A, B, C, D, E, F = n
            return (a*A+b*C, a*B+b*D, c*A+d*C, c*B+d*D, e*A+f*C+E, e*B+f*D+F)

        def inspect(stream, resources, matrix=(1, 0, 0, 1, 0, 0), depth=0):
            nonlocal image_area, images
            if depth > 8:
                raise ValueError('Deep form nesting')
            resources = resources.get_object() if resources else {}
            stack = []
            if stream is None:
                return
            for operands, operator in ContentStream(stream, page.pdf).operations:
                if operator == b'q':
                    stack.append(matrix)
                elif operator == b'Q':
                    if not stack:
                        raise ValueError('Unbalanced graphics state')
                    matrix = stack.pop()
                elif operator == b'cm':
                    matrix = multiply(tuple(float(v) for v in operands), matrix)
                elif operator == b'INLINE IMAGE' or (operator == b'Tr' and int(operands[0]) in (3, 4, 5, 6, 7)):
                    raise ValueError('Image or hidden text')
                elif operator == b'Do':
                    obj = resources['/XObject'].get_object()[operands[0]].get_object()
                    if obj.get('/Subtype') == '/Form':
                        form_matrix = tuple(float(v) for v in obj.get('/Matrix', (1, 0, 0, 1, 0, 0)))
                        inspect(obj, obj.get('/Resources', resources), multiply(form_matrix, matrix), depth + 1)
                    elif obj.get('/Subtype') == '/Image':
                        images += 1
                        a, b, c, d, e, f = matrix
                        ys = [f, b+f, d+f, b+d+f]
                        bottom, top = float(bounds.bottom), float(bounds.top)
                        if not (max(ys) <= bottom + height*.15 or min(ys) >= top - height*.15):
                            raise ValueError('Image in policy body')
                        image_area += abs(a*d-b*c)
                        if image_area > width*height*.025:
                            raise ValueError('Substantial image')
                    else:
                        raise ValueError('Unsupported drawn object')
            if stack:
                raise ValueError('Unbalanced graphics state')

        inspect(page.get_contents(), page.get('/Resources'))
        text = (page.extract_text() or '').strip()
        if (len(text) < (800 if images else 80)
                or len(re.findall(r'\w+', text)) < (100 if images else 12)
                or '\ufffd' in text or '(cid:' in text.lower()
                or any(ord(c) < 32 and c not in '\n\r\t' for c in text)):
            return None
        readable = sum(c.isalnum() or c.isspace() or c in '.,:;!?%₹()/-–—' for c in text)
        if readable / len(text) < .95 or sum(c.isalpha() for c in text) / len(text) < .45:
            return None
        return text
    except Exception:
        return None


def _process(data, mime, timeout=35):
    return docai().process_document(
        request=documentai.ProcessRequest(name=docai_processor_name(),
            raw_document=documentai.RawDocument(content=data, mime_type=mime), imageless_mode=True),
        retry=None, timeout=timeout,
    ).document


def ocr_pdf(pdf_bytes: bytes, *, saved_pages=None, on_pages=None) -> list[dict]:
    """Read suitable native text and OCR other pages, keeping original numbers.

    Saved pages must belong to this guest/content hash (enforced by policy_ingest).
    Failed groups split; a one-page failure gets one retry. At most four recovery
    steps, two quota-window waits and 210 seconds bound this OCR invocation.
    """
    reader = _reader(pdf_bytes)
    total = len(reader.pages)
    saved = saved_pages or {}
    if any(not isinstance(n, int) or n < 1 or n > total for n in saved):
        saved = {}
    result = dict(saved)
    native = []
    for index, page in enumerate(reader.pages, 1):
        if index not in result:
            text = _native_text(page)
            if text is not None:
                native.append({'page': index, 'text': text})
    if native:
        if on_pages:
            on_pages(native, total)
        result.update({page['page']: page['text'] for page in native})
    log.info('Policy PDF reading total=%s saved=%s native=%s ocr_pending=%s',
             total, len(saved), len(native), total - len(result))
    deadline = time.monotonic() + 210
    recovery = 4
    quota_waits = 2

    def read(start, end):
        nonlocal recovery, quota_waits
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise OcrProcessingError(InternalServerError('OCR recovery deadline'), start + 1, end)
        try:
            doc = _process(_pdf_bytes(reader.pages[start:end]), 'application/pdf', timeout=min(35, remaining))
            numbers = [p.page_number for p in doc.pages]
            if sorted(numbers) != list(range(1, end - start + 1)):
                raise InternalServerError('OCR returned an incomplete page group')
        except GoogleAPIError as exc:
            if int(exc.code) == 429:
                # Splitting would consume more quota. Wait for a quota window,
                # then retry this exact range; keep successful pages untouched.
                if quota_waits <= 0 or deadline - time.monotonic() < 65:
                    raise OcrProcessingError(exc, start + 1, end) from exc
                quota_waits -= 1
                log.warning('PDF OCR quota wait start=%s end=%s remaining_waits=%s', start + 1, end, quota_waits)
                time.sleep(60)
                read(start, end)
                return
            if int(exc.code) not in (500, 503, 504) or recovery <= 0 or time.monotonic() >= deadline:
                raise OcrProcessingError(exc, start + 1, end) from exc
            # One recovery step permits two smaller calls after the failed call.
            recovery -= 1
            log.warning('PDF OCR recovery start=%s end=%s code=%s remaining=%s', start + 1, end, int(exc.code), recovery)
            if end - start > 1:
                middle = (start + end) // 2
                read(start, middle)
                read(middle, end)
            else:
                time.sleep(min(1, max(0, deadline - time.monotonic())))
                read(start, end)
            return
        batch = [{'page': start + p.page_number, 'text': _page_text(doc, p)} for p in doc.pages]
        if on_pages:
            on_pages(batch, total)
        result.update({p['page']: p['text'] for p in batch})

    start = 0
    while start < total:
        if start + 1 in result:
            start += 1
            continue
        end = start + 1
        while end < total and end - start < PAGES_PER_REQUEST and end + 1 not in result:
            end += 1
        read(start, end)
        start = end
    return [{'page': n, 'text': result[n]} for n in range(1, total + 1)]


def ocr_first_page(data: bytes, mime: str = 'application/pdf') -> str:
    """Read only page one (or a whole photo) for classification/readability."""
    if mime == 'application/pdf':
        page = PdfReader(BytesIO(data)).pages[0]
        text = _native_text(page)
        if text is not None:
            return text
        data = _pdf_bytes([page])
    # Classification has no page groups to split; one bounded transient retry.
    for attempt in range(2):
        try:
            return _process(data, mime).text
        except GoogleAPIError as exc:
            if int(exc.code) not in (500, 503, 504) or attempt:
                raise
            time.sleep(1)
