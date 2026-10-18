from io import BytesIO
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from google.api_core.exceptions import Forbidden, InternalServerError
from google.cloud import documentai_v1 as documentai
from pypdf import PdfReader, PdfWriter

from app.services import ocr, policy_ingest
from app.core import session


def pdf(count):
    writer = PdfWriter()
    for _ in range(count):
        writer.add_blank_page(width=595, height=841)
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


def document(count):
    text = 'Original page text.'
    return documentai.Document(text=text, pages=[documentai.Document.Page(
        page_number=n, layout=documentai.Document.Page.Layout(text_anchor=documentai.Document.TextAnchor(
            text_segments=[documentai.Document.TextAnchor.TextSegment(start_index=0, end_index=len(text))])))
        for n in range(1, count + 1)])


class OcrRecoveryTests(unittest.TestCase):
    def setUp(self):
        patcher = patch.object(ocr, 'get_settings', return_value=SimpleNamespace(max_policy_pages=100))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_failed_group_splits_without_losing_original_page_numbers(self):
        saved = []
        with patch.object(ocr, 'PAGES_PER_REQUEST', 15), \
             patch.object(ocr, '_process', side_effect=[InternalServerError('private'), document(7), document(8), document(1)]) as call:
            result = ocr.ocr_pdf(pdf(16), on_pages=lambda batch, total: saved.append((batch, total)))
        self.assertEqual([p['page'] for p in result], list(range(1, 17)))
        self.assertEqual([[p['page'] for p in b] for b, _ in saved], [list(range(1, 8)), list(range(8, 16)), [16]])
        self.assertTrue(all(total == 16 for _, total in saved))
        self.assertEqual(call.call_count, 4)

    def test_partial_saved_groups_are_skipped_on_retry(self):
        previous = {n: f'Saved {n}' for n in range(1, 8)}
        def process(data, mime, timeout):
            return document(len(PdfReader(BytesIO(data)).pages))
        with patch.object(ocr, '_process', side_effect=process) as call:
            result = ocr.ocr_pdf(pdf(16), saved_pages=previous)
        self.assertEqual(call.call_count, 2)
        self.assertEqual([len(PdfReader(BytesIO(c.args[0])).pages) for c in call.call_args_list], [5, 4])
        self.assertEqual(result[6], {'page': 7, 'text': 'Saved 7'})
        self.assertEqual([p['page'] for p in result], list(range(1, 17)))

    def test_persistent_failure_is_bounded_and_does_not_checkpoint_missing_pages(self):
        checkpoint = Mock()
        with patch.object(ocr, '_process', side_effect=InternalServerError('private text')), patch.object(ocr.time, 'sleep'), \
             patch.object(ocr, 'log'):
            with self.assertRaises(ocr.OcrProcessingError) as caught:
                ocr.ocr_pdf(pdf(15), on_pages=checkpoint)
        self.assertEqual(caught.exception.code, 500)
        self.assertNotIn('private text', str(caught.exception))
        checkpoint.assert_not_called()

    def test_auth_errors_do_not_retry_or_change_status(self):
        with patch.object(ocr, '_process', side_effect=Forbidden('private')) as call:
            with self.assertRaises(ocr.OcrProcessingError) as caught:
                ocr.ocr_pdf(pdf(2))
        self.assertEqual(caught.exception.code, 403)
        self.assertEqual(call.call_count, 1)

    def test_incomplete_provider_response_cannot_be_saved_as_complete(self):
        checkpoint = Mock()
        with patch.object(ocr, '_process', return_value=document(0)) as call, patch.object(ocr.time, 'sleep'), patch.object(ocr, 'log'):
            with self.assertRaises(ocr.OcrProcessingError):
                ocr.ocr_pdf(pdf(2), on_pages=checkpoint)
        self.assertLessEqual(call.call_count, 5)
        checkpoint.assert_not_called()

    def test_first_page_classification_has_one_transient_retry(self):
        with patch.object(ocr, '_process', side_effect=[InternalServerError('busy'), document(1)]) as call, patch.object(ocr.time, 'sleep'):
            self.assertEqual(ocr.ocr_first_page(pdf(3)), 'Original page text.')
        self.assertEqual(call.call_count, 2)

    def test_ingestion_checkpoints_ocr_before_later_group_failure(self):
        token = session.set_session(session.new_session_id())
        self.addCleanup(session.reset_session, token)
        def fail(data, **kwargs):
            kwargs['on_pages']([{'page': 1, 'text': 'Saved original text'}], 2)
            raise ocr.OcrProcessingError(InternalServerError('private'), 2, 2)
        with patch.object(policy_ingest.store, 'get_policy', return_value=None), \
             patch.object(policy_ingest.store, 'save_original') as original, \
             patch.object(policy_ingest.store, 'save_policy') as save, \
             patch.object(policy_ingest.store, 'save_pages') as pages, \
             patch.object(policy_ingest.store, 'set_active_policy') as active, \
             patch.object(policy_ingest, 'ocr_pdf', side_effect=fail):
            with self.assertRaises(ocr.OcrProcessingError):
                policy_ingest.ingest_policy(pdf(2), 'fixture.pdf')
        original.assert_called_once()
        self.assertEqual(pages.call_args.args[1], [{'page': 1, 'text': 'Saved original text'}])
        self.assertTrue(any(c.args[1].get('pageCount') == 2 for c in save.call_args_list))
        self.assertEqual(save.call_args.args[1]['status'], 'failed')
        active.assert_not_called()
