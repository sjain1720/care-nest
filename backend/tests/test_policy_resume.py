import unittest
from unittest.mock import Mock, patch
from google.genai import errors
from app.services import policy_ingest
from app.services.clauses import Clause


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
             patch.object(policy_ingest.store, 'load_clause_index', return_value={}), \
             patch.object(policy_ingest.store, 'set_active_policy') as active, \
             patch.object(policy_ingest, 'ocr_pdf', return_value=[{'page': 1, 'text': 'Fresh reading'}]) as ocr, \
             patch.object(policy_ingest, 'split_into_clauses', return_value=[Clause('p001-c01', 1, 'Page 1', '', 'Wording')]), \
             patch.object(policy_ingest.time, 'sleep'), \
             patch.object(policy_ingest, 'embed_texts', side_effect=errors.ClientError(429, {'error': {'message': 'Busy'}}) if error else None, return_value=[[0.0] * 768]), \
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

    def test_retry_preserves_successful_batches_and_indexes_only_remaining_text(self):
        clauses = [Clause(f'c{i}', 1, 'Page 1', '', f'Wording {i}') for i in range(51)]
        indexed = {}
        def save_batch(policy_id, group, vectors):
            indexed.update({c.clause_id: policy_ingest.store.clause_index_stamp(c) for c in group})
        with patch.object(policy_ingest.store, 'get_policy', return_value={'status': 'failed', 'pageCount': 1}), \
             patch.object(policy_ingest.store, 'load_pages', return_value={1: 'Wording'}), \
             patch.object(policy_ingest.store, 'load_clause_index', side_effect=lambda _: dict(indexed)), \
             patch.object(policy_ingest.store, 'save_policy'), \
             patch.object(policy_ingest.store, 'save_clauses', side_effect=save_batch), \
             patch.object(policy_ingest.store, 'set_active_policy') as active, \
             patch.object(policy_ingest, 'ocr_pdf') as ocr, \
             patch.object(policy_ingest, 'split_into_clauses', return_value=clauses), \
             patch.object(policy_ingest, 'extract_policy_facts'), \
             patch.object(policy_ingest, 'build_policy_facts', return_value=Mock(model_dump=lambda: {})), \
             patch.object(policy_ingest.time, 'sleep') as sleep, \
             patch.object(policy_ingest, 'embed_texts', side_effect=[[[0.0]*768]*50, errors.ClientError(429, {'error': {'message': 'Busy'}}), errors.ClientError(429, {'error': {'message': 'Still busy'}}), [[0.0]*768]]) as embed:
            with self.assertRaises(errors.ClientError):
                policy_ingest.ingest_policy(b'fixture', 'fixture.pdf')
            self.assertEqual(len(indexed), 50)
            sleep.assert_called_once_with(60)
            active.assert_not_called()
            policy_ingest.ingest_policy(b'fixture', 'fixture.pdf')
            self.assertEqual(len(embed.call_args_list[-1].args[0]), 1)
            self.assertEqual(len(indexed), 51)
            active.assert_called_once()
            ocr.assert_not_called()

    def test_one_quota_window_can_complete_without_a_manual_retry(self):
        clause = Clause('c1', 1, 'Page 1', '', 'Wording')
        with patch.object(policy_ingest.store, 'get_policy', return_value={'status': 'failed', 'pageCount': 1}), \
             patch.object(policy_ingest.store, 'load_pages', return_value={1: 'Wording'}), \
             patch.object(policy_ingest.store, 'load_clause_index', return_value={}), \
             patch.object(policy_ingest.store, 'save_policy'), \
             patch.object(policy_ingest.store, 'save_clauses') as saved, \
             patch.object(policy_ingest.store, 'set_active_policy') as active, \
             patch.object(policy_ingest, 'split_into_clauses', return_value=[clause]), \
             patch.object(policy_ingest, 'extract_policy_facts'), \
             patch.object(policy_ingest, 'build_policy_facts', return_value=Mock(model_dump=lambda: {})), \
             patch.object(policy_ingest.time, 'sleep') as sleep, \
             patch.object(policy_ingest, 'embed_texts', side_effect=[errors.ClientError(429, {'error': {'message': 'Busy'}}), [[0.0]*768]]):
            policy_ingest.ingest_policy(b'fixture', 'fixture.pdf')
            sleep.assert_called_once_with(60)
            saved.assert_called_once()
            active.assert_called_once()

    def test_index_stamp_invalidates_changed_text_or_encoder(self):
        clause = Clause('same-id', 1, 'Page 1', '', 'Original')
        stamp = policy_ingest.store.clause_index_stamp(clause)
        clause.text = 'Changed'
        self.assertNotEqual(stamp, policy_ingest.store.clause_index_stamp(clause))
        with patch('app.services.policy_store.get_settings', return_value=Mock(embedding_model='another-encoder')):
            clause.text = 'Original'
            self.assertNotEqual(stamp, policy_ingest.store.clause_index_stamp(clause))
