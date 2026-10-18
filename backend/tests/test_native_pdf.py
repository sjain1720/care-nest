from io import BytesIO
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject, ArrayObject
from app.services import ocr
from tests.test_ocr_recovery import document

TEXT = 'Policy wording describes benefits exclusions waiting periods and conditions. Please read the issued schedule for your selected benefits.'


def fixture(kinds):
    writer = PdfWriter()
    for kind in kinds:
        page = writer.add_blank_page(width=595, height=841)
        if kind == 'blank':
            continue
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
        resources = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): font})})
        page[NameObject('/Resources')] = resources
        stream = DecodedStreamObject()
        text = 'Policy' if kind == 'sparse' else TEXT*10 if kind in ('logo', 'body_image', 'large_logo', 'form') else TEXT
        stream.set_data(f'BT /F1 12 Tf 50 700 Td {"3 Tr" if kind == "hidden" else ""} ({text}) Tj ET'.encode())
        page[NameObject('/Contents')] = writer._add_object(stream)
        if kind in ('image', 'form', 'logo', 'body_image', 'large_logo'):
            resources[NameObject('/XObject')] = DictionaryObject({NameObject('/X1'): DictionaryObject({NameObject('/Subtype'): NameObject('/Form' if kind == 'form' else '/Image')})})
        if kind in ('image', 'form', 'logo', 'body_image', 'large_logo'):
            transform = '40 0 0 20 40 800' if kind == 'logo' else '40 0 0 20 40 400' if kind == 'body_image' else '500 0 0 80 40 760' if kind == 'large_logo' else '500 0 0 700 40 40'
            stream.set_data(stream.get_data() + f' q {transform} cm /X1 Do Q'.encode())
        if kind == 'annotation':
            page[NameObject('/Annots')] = ArrayObject([DictionaryObject({NameObject('/Subtype'): NameObject('/Text')})])
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


class NativePdfTests(unittest.TestCase):
    def setUp(self):
        settings = patch.object(ocr, 'get_settings', return_value=SimpleNamespace(max_policy_pages=100))
        settings.start()
        self.addCleanup(settings.stop)

    def test_native_policy_needs_no_ocr_and_checkpoints_original_page_numbers(self):
        saved = []
        with patch.object(ocr, '_process') as call:
            result = ocr.ocr_pdf(fixture(['text', 'text']), on_pages=lambda b, n: saved.append((b, n)))
        call.assert_not_called()
        self.assertEqual(result, [{'page': 1, 'text': TEXT}, {'page': 2, 'text': TEXT}])
        self.assertEqual(saved, [(result, 2)])

    def test_mixed_pdf_ocrs_only_untrusted_pages_preserving_order(self):
        def process(data, mime, timeout):
            return document(len(PdfReader(BytesIO(data)).pages))
        with patch.object(ocr, '_process', side_effect=process) as call:
            result = ocr.ocr_pdf(fixture(['text', 'image', 'blank', 'text', 'hidden']))
        self.assertEqual([len(PdfReader(BytesIO(c.args[0])).pages) for c in call.call_args_list], [2, 1])
        self.assertEqual([p['page'] for p in result], [1, 2, 3, 4, 5])
        self.assertEqual(result[3]['text'], TEXT)
        self.assertEqual(result[4]['text'], 'Original page text.')

    def test_sparse_hidden_image_form_and_annotation_pages_use_ocr(self):
        for kind in ('sparse', 'hidden', 'image', 'form', 'body_image', 'large_logo', 'annotation', 'blank'):
            with self.subTest(kind=kind):
                page = PdfReader(BytesIO(fixture([kind]))).pages[0]
                self.assertIsNone(ocr._native_text(page))

    def test_extract_failure_falls_back(self):
        page = PdfReader(BytesIO(fixture(['text']))).pages[0]
        with patch.object(page, 'extract_text', side_effect=ValueError('malformed')):
            self.assertIsNone(ocr._native_text(page))

    def test_saved_page_is_not_reinterpreted_on_retry(self):
        with patch.object(ocr, '_process') as call:
            result = ocr.ocr_pdf(fixture(['hidden', 'text']), saved_pages={1: 'Previously saved OCR'})
        call.assert_not_called()
        self.assertEqual(result[0]['text'], 'Previously saved OCR')

    def test_native_first_page_classification_needs_no_ocr(self):
        with patch.object(ocr, '_process') as call:
            self.assertEqual(ocr.ocr_first_page(fixture(['text'])), TEXT)
        call.assert_not_called()

    def test_document_ai_uses_imageless_response_without_changing_processor(self):
        with patch.object(ocr, 'docai') as client, patch.object(ocr, 'docai_processor_name', return_value='configured-processor'):
            ocr._process(b'fixture', 'application/pdf')
        kwargs = client.return_value.process_document.call_args.kwargs
        self.assertTrue(kwargs['request'].imageless_mode)
        self.assertEqual(kwargs['request'].name, 'configured-processor')
        self.assertEqual(kwargs['timeout'], 35)
        self.assertIsNone(kwargs['retry'])

    def test_small_header_logo_does_not_force_ocr_of_strong_text(self):
        page = PdfReader(BytesIO(fixture(['logo']))).pages[0]
        self.assertEqual(ocr._native_text(page), TEXT*10)

    def test_unused_image_resources_do_not_classify_text_page_as_scanned(self):
        page = PdfReader(BytesIO(fixture(['text']))).pages[0]
        page['/Resources'][NameObject('/XObject')] = DictionaryObject({NameObject('/Unused'): DictionaryObject({NameObject('/Subtype'): NameObject('/Image')})})
        self.assertEqual(ocr._native_text(page), TEXT)

    def test_ocr_quota_wait_retries_same_group_without_splitting(self):
        from google.api_core.exceptions import ResourceExhausted
        with patch.object(ocr, '_process', side_effect=[ResourceExhausted('quota'), document(3)]) as call, patch.object(ocr.time, 'sleep') as sleep:
            pages = ocr.ocr_pdf(fixture(['blank']*3))
        self.assertEqual(len(pages), 3)
        sleep.assert_called_once_with(60)
        self.assertEqual([len(PdfReader(BytesIO(c.args[0])).pages) for c in call.call_args_list], [3,3])

    def test_persistent_ocr_quota_wait_is_bounded_and_does_not_checkpoint(self):
        from google.api_core.exceptions import ResourceExhausted
        from unittest.mock import Mock
        checkpoint = Mock()
        with patch.object(ocr, '_process', side_effect=ResourceExhausted('quota')) as call, patch.object(ocr.time, 'sleep') as sleep:
            with self.assertRaises(ocr.OcrProcessingError) as caught:
                ocr.ocr_pdf(fixture(['blank']*3), on_pages=checkpoint)
        self.assertEqual(caught.exception.code, 429)
        self.assertEqual(call.call_count, 3)
        self.assertEqual(sleep.call_count, 2)
        checkpoint.assert_not_called()

    def test_native_checkpoint_survives_later_ocr_failure(self):
        from google.api_core.exceptions import Forbidden
        saved=[]
        with patch.object(ocr, '_process', side_effect=Forbidden('denied')):
            with self.assertRaises(ocr.OcrProcessingError):
                ocr.ocr_pdf(fixture(['text','image']), on_pages=lambda b,n:saved.extend(b))
        self.assertEqual(saved, [{'page':1,'text':TEXT}])
