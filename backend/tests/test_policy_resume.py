import unittest
from unittest.mock import Mock, patch
from google.genai import errors
from app.services import policy_ingest


class PolicyResumeTests(unittest.TestCase):
    def setUp(self):
        from app.core.session import set_session, reset_session, new_session_id
        token = set_session(new_session_id())
        self.addCleanup(reset_session, token)

    def run_ingest(self, saved, error=False):
        # The existing record belongs to the derived guest/content-hash ID.
        with patch.object(policy_ingest.store, 'get_policy', return_value={'status': 'failed', 'pageCount': 2}), \
             patch.object(policy_ingest.store, 'load_pages', return_value=saved), \
             patch.object(policy_ingest.store, 'save_policy') as save, \
             patch.object(policy_ingest.store, 'save_original'), \
             patch.object(policy_ingest.store, 'save_pages'), \
             patch.object(policy_ingest.store, 'save_clauses'), \
             patch.object(policy_ingest.store, 'set_active_policy') as active, \
             patch.object(policy_ingest, 'ocr_pdf', return_value=[{'page': 1, 'text': 'Fresh reading'}]) as ocr, \
             patch.object(policy_ingest, 'split_into_clauses', return_value=[]), \
             patch.object(policy_ingest, 'embed_texts', side_effect=errors.ClientError(429, {'error': {'message': 'Busy'}}) if error else None, return_value=[]), \
             patch.object(policy_ingest, 'extract_policy_facts'), \
             patch.object(policy_ingest, 'build_policy_facts', return_value=Mock(model_dump=lambda: {})):
            if error:
                with self.assertRaises(errors.ClientError):
                    policy_ingest.ingest_policy(b'fixture', 'fixture.pdf')
                active.assert_not_called()
                failure = save.call_args.args[1]
                self.assertEqual(failure['status'], 'failed')
                self.assertEqual(failure['processingStage'], 'embedding_clauses')
                self.assertEqual(failure['lastErrorCode'], 429)
            else:
                policy_ingest.ingest_policy(b'fixture', 'fixture.pdf')
                active.assert_called_once()
            return ocr.call_count

    def test_complete_saved_reading_skips_ocr_on_retry(self):
        self.assertEqual(self.run_ingest({1: 'One', 2: 'Two'}), 0)

    def test_partial_or_wrong_page_numbers_are_not_reused(self):
        self.assertEqual(self.run_ingest({1: 'One'}), 1)
        self.assertEqual(self.run_ingest({2: 'Two', 3: 'Wrong page'}), 1)

    def test_google_failure_records_stage_and_does_not_activate(self):
        self.assertEqual(self.run_ingest({1: 'One', 2: 'Two'}, error=True), 0)
