"""Prototype release gates: reject forged/expired identities and isolate guests."""
import asyncio
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from app.main import app
from app.core import session
from app.services import session_registry, policy_store, policy_ingest
from app.services.data_lifecycle import delete_guest


class RegistryTests(unittest.TestCase):
    def resolve(self, candidate, record=None):
        database = Mock()
        snap = database.collection.return_value.document.return_value.get.return_value
        snap.exists = record is not None
        snap.to_dict.return_value = record
        with patch.object(session_registry, "db", return_value=database):
            result = session_registry.resolve_session(candidate)
        return result, database

    def test_unissued_well_shaped_cookie_is_replaced(self):
        forged = session.new_session_id()
        (sid, deadline), database = self.resolve(forged)
        self.assertNotEqual(sid, forged)
        self.assertGreater(deadline, datetime.now(timezone.utc))
        database.collection.return_value.document.return_value.create.assert_called_once()

    def test_expired_and_revoked_cookies_are_replaced(self):
        sid = session.new_session_id()
        now = datetime.now(timezone.utc)
        for record in ({"expiresAt": now - timedelta(seconds=1)},
                       {"expiresAt": now + session.TTL, "revoked": True}):
            self.assertNotEqual(self.resolve(sid, record)[0][0], sid)

    def test_valid_identity_keeps_original_deadline(self):
        sid = session.new_session_id()
        deadline = datetime.now(timezone.utc) + timedelta(hours=3)
        result, database = self.resolve(sid, {"expiresAt": deadline})
        self.assertEqual(result, (sid, deadline))
        database.collection.return_value.document.return_value.create.assert_not_called()

    def test_child_workspace_id_is_not_accepted_as_a_browser_cookie(self):
        child = session.new_session_id()
        result, _ = self.resolve(child, {'expiresAt': datetime.now(timezone.utc) + session.TTL,
                                         'parentSessionId': session.new_session_id()})
        self.assertNotEqual(result[0], child)


class TwoVisitorTests(unittest.TestCase):
    def test_identical_private_policy_bytes_do_not_share_personal_extraction(self):
        results = []
        with patch.object(policy_ingest.store, 'get_policy', return_value=None), \
             patch.object(policy_ingest.store, 'save_policy') as save, \
             patch.object(policy_ingest.store, 'save_original'), \
             patch.object(policy_ingest.store, 'save_pages'), \
             patch.object(policy_ingest.store, 'save_clauses'), \
             patch.object(policy_ingest.store, 'set_active_policy'), \
             patch.object(policy_ingest, 'ocr_pdf', return_value=[{'page': 1, 'text': 'Synthetic wording'}]), \
             patch.object(policy_ingest, 'split_into_clauses', return_value=[]), \
             patch.object(policy_ingest, 'embed_texts', return_value=[]), \
             patch.object(policy_ingest, 'extract_policy_facts'), \
             patch.object(policy_ingest, 'build_policy_facts'):
            for _ in range(2):
                sid = session.new_session_id()
                token = session.set_session(sid)
                try:
                    result = policy_ingest.ingest_policy(b'same synthetic bytes', 'wording.pdf')
                    results.append(result.policyId)
                    self.assertEqual(next(call.args[1]['ownerSessionId'] for call in reversed(save.call_args_list) if 'ownerSessionId' in call.args[1]), sid)
                finally:
                    session.reset_session(token)
        self.assertNotEqual(results[0], results[1])

    def test_cookie_jars_and_stream_workers_have_separate_policy_context(self):
        issued, policies = {}, {}

        def resolve(candidate):
            sid = candidate if candidate in issued else session.new_session_id()
            issued.setdefault(sid, datetime.now(timezone.utc) + session.TTL)
            return sid, issued[sid]

        def answer(question, on_step=None, language="en", original_question=None):
            from app.schemas import AnswerCard, AskResponse
            return AskResponse(steps=[], answer=AnswerCard(
                verdict="info", headline="Selected document", summary=policies.get(session.session_id(), "No policy"),
                citations=[], toConfirm=[]))

        with patch("app.core.session_middleware.resolve_session", side_effect=resolve), \
             patch("app.routers.copilot.answer", side_effect=answer):
            with TestClient(app) as a, TestClient(app) as b:
                a.get('/api/health'); b.get('/api/health')
                a_id, b_id = a.cookies.get(session.COOKIE), b.cookies.get(session.COOKIE)
                self.assertNotEqual(a_id, b_id)
                policies[a_id] = "A private policy"
                policies[b_id] = "B private policy"
                for client, own, other in ((a, 'A private policy', 'B private policy'), (b, 'B private policy', 'A private policy')):
                    result = client.post('/api/copilot/ask/stream', json={"question": "What is my cover?"})
                    self.assertEqual(result.status_code, 200)
                    self.assertIn(own, result.text)
                    self.assertNotIn(other, result.text)

    def test_owned_policy_and_claim_deletion_preserves_demo(self):
        sid = session.new_session_id()
        database = Mock()
        private, demo = Mock(id="private"), Mock(id="demo")
        private.to_dict.return_value = {"isDemoTemplate": False}
        demo.to_dict.return_value = {"isDemoTemplate": True}
        database.collection.return_value.where.return_value.stream.return_value = [private, demo]
        storage = Mock()
        blob = Mock()
        storage.list_blobs.return_value = [blob]
        with patch('app.services.data_lifecycle.db', return_value=database), \
             patch('app.services.data_lifecycle.bucket', return_value=storage), \
             patch('app.services.data_lifecycle.revoke_session') as revoke, \
             patch('app.services.data_lifecycle.case_store.delete_case') as claims, \
             patch('app.services.data_lifecycle.policy_store.delete_session_state') as state:
            delete_guest(sid)
        revoke.assert_called_once_with(sid)
        claims.assert_called_once()
        state.assert_called_once()
        blob.delete.assert_called_once()
        database.recursive_delete.assert_any_call(private.reference)

    def test_delete_endpoint_expires_cookie_without_middleware_restoring_it(self):
        sid = session.new_session_id()
        with patch('app.core.session_middleware.resolve_session', return_value=(sid, datetime.now(timezone.utc) + session.TTL)), \
             patch('app.routers.session.delete_guest') as delete:
            with TestClient(app) as client:
                response = client.delete('/api/session')
        self.assertEqual(response.status_code, 204)
        self.assertEqual(len(response.headers.get_list('set-cookie')), 1)
        self.assertIn('Max-Age=0', response.headers['set-cookie'])
        delete.assert_called_once_with(sid)
