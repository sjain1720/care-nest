import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from google.genai import errors

from app.services import embeddings, policy_ingest
from app.services.clauses import Clause


class EmbeddingBatchTests(unittest.TestCase):
    def test_count_and_payload_limits_preserve_order_and_whole_passages(self):
        for texts, expected in [(['short'] * 101, [50, 50, 1]),
                                (['x' * 1500] * 50, [38, 12]),
                                (['अ' * 500] * 50, [38, 12]),
                                ([], [])]:
            with self.subTest(expected=expected, count=len(texts)):
                groups = list(embeddings.embedding_batches(texts))
                self.assertEqual([len(g) for g in groups], expected)
                self.assertEqual([t for g in groups for t in g], texts)

    def test_helper_sends_fifty_inputs_without_changing_vectors_or_truncating(self):
        client = Mock()
        client.models.embed_content.side_effect = lambda **kw: SimpleNamespace(
            embeddings=[SimpleNamespace(values=[float(t), 1.0]) for t in kw['contents']])
        texts = [str(i) for i in range(51)]
        with patch.object(embeddings, 'gemini', return_value=client):
            result = embeddings.embed_texts(texts, 'RETRIEVAL_DOCUMENT')
        self.assertEqual(result, [[float(i), 1.0] for i in range(51)])
        self.assertEqual([len(c.kwargs['contents']) for c in client.models.embed_content.call_args_list], [50, 1])
        config = client.models.embed_content.call_args.kwargs['config']
        self.assertFalse(config.auto_truncate)
        self.assertEqual(config.output_dimensionality, 768)

    def test_token_rejection_splits_then_checkpoints_each_successful_request(self):
        from app.core.session import set_session, reset_session, new_session_id
        token = set_session(new_session_id())
        self.addCleanup(reset_session, token)
        clauses = [Clause(f'c{i}', 1, 'Page 1', '', f'Wording {i}') for i in range(50)]
        calls, saved = [], []

        def embed(texts, task):
            calls.append(len(texts))
            if len(texts) == 50:
                raise errors.ClientError(400, {'error': {'message': 'Input exceeds token limit'}})
            return [[0.0] * 768 for _ in texts]

        with patch.object(policy_ingest.store, 'get_policy', return_value={'status': 'failed', 'pageCount': 1}), \
             patch.object(policy_ingest.store, 'load_pages', return_value={1: 'Wording'}), \
             patch.object(policy_ingest.store, 'load_clause_index', return_value={}), \
             patch.object(policy_ingest.store, 'save_policy'), \
             patch.object(policy_ingest.store, 'save_clauses', side_effect=lambda _, group, vectors: saved.append(len(group))), \
             patch.object(policy_ingest.store, 'set_active_policy') as active, \
             patch.object(policy_ingest, 'split_into_clauses', return_value=clauses), \
             patch.object(policy_ingest, 'extract_policy_facts'), \
             patch.object(policy_ingest, 'build_policy_facts', return_value=Mock(model_dump=lambda: {})), \
             patch.object(policy_ingest, 'embed_texts', side_effect=embed):
            policy_ingest.ingest_policy(b'fixture', 'fixture.pdf')
        self.assertEqual(calls, [50, 25, 25])
        self.assertEqual(saved, [25, 25])
        active.assert_called_once()

    def test_non_token_bad_requests_are_not_reclassified_as_batch_size_errors(self):
        self.assertFalse(embeddings.is_token_limit_error(
            errors.ClientError(400, {'error': {'message': 'Invalid task type'}})))
        self.assertFalse(embeddings.is_token_limit_error(
            errors.ClientError(429, {'error': {'message': 'Token quota exhausted'}})))
