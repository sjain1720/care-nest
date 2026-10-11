from io import BytesIO

from google.cloud import documentai_v1 as documentai
from pypdf import PdfReader, PdfWriter

from app.core.config import get_settings
from app.core.gcp import docai, docai_processor_name

# Online (synchronous) OCR accepts at most 15 pages per request.
PAGES_PER_REQUEST = 15


class PdfTooLongError(ValueError):
    pass


def _split_pdf(pdf_bytes: bytes):
    reader = PdfReader(BytesIO(pdf_bytes))
    total = len(reader.pages)
    limit = get_settings().max_policy_pages
    if total > limit:
        raise PdfTooLongError(f"PDF has {total} pages; the limit is {limit}.")

    for start in range(0, total, PAGES_PER_REQUEST):
        writer = PdfWriter()
        for i in range(start, min(start + PAGES_PER_REQUEST, total)):
            writer.add_page(reader.pages[i])
        buf = BytesIO()
        writer.write(buf)
        yield start, buf.getvalue()


def _page_text(document: documentai.Document, page: documentai.Document.Page) -> str:
    return "".join(
        document.text[seg.start_index:seg.end_index] for seg in page.layout.text_anchor.text_segments
    ).strip()


def ocr_pdf(pdf_bytes: bytes) -> list[dict]:
    """Return [{"page": 1-based page number in the original PDF, "text": ...}, ...]."""
    pages: list[dict] = []
    for offset, chunk in _split_pdf(pdf_bytes):
        result = docai().process_document(
            request=documentai.ProcessRequest(
                name=docai_processor_name(),
                raw_document=documentai.RawDocument(content=chunk, mime_type="application/pdf"),
            )
        )
        doc = result.document
        for page in doc.pages:
            pages.append({"page": offset + page.page_number, "text": _page_text(doc, page)})
    return pages


def ocr_first_page(pdf_bytes: bytes) -> str:
    """Text of page 1 only – a cheap way to tell what kind of document this is."""
    writer = PdfWriter()
    writer.add_page(PdfReader(BytesIO(pdf_bytes)).pages[0])
    buf = BytesIO()
    writer.write(buf)
    result = docai().process_document(
        request=documentai.ProcessRequest(
            name=docai_processor_name(),
            raw_document=documentai.RawDocument(content=buf.getvalue(), mime_type="application/pdf"),
        )
    )
    return result.document.text
