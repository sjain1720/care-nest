"""Legacy root sample selections must not supply personal coverage evidence."""
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.core import session
from app.routers import policy
from app.services import copilot, policy_store


class LegacySamplePolicyTests(unittest.TestCase):
    def setUp(self):
        self.root = session.new_session_id()
        token = session.set_session(self.root)
        root_token = session.set_root_session(self.root)
        self.addCleanup(session.reset_session, token)
        self.addCleanup(session.reset_root_session, root_token)
        state = patch.object(policy_store, '_session_state', return_value={'activePolicyId': 'demo-old-sample'})
        state.start()
        self.addCleanup(state.stop)

    def test_personal_sample_is_not_an_active_policy_or_source(self):
        with patch.object(policy_store, 'get_policy') as load:
            self.assertIsNone(policy_store.get_active_policy_id())
            self.assertIsNone(policy_store.get_active_policy())
            self.assertTrue(policy_store.has_legacy_sample_policy())
            load.assert_not_called()
        for read in (policy.get_policy, policy.get_policy_document):
            with self.assertRaises(HTTPException) as caught:
                read()
            self.assertEqual(caught.exception.status_code, 404)
            self.assertEqual(caught.exception.detail['code'], 'sample_policy_requires_upload')

    def test_chat_requests_upload_before_router_balance_or_investigation(self):
        with patch.object(copilot, 'route', side_effect=AssertionError('Router must not run')), \
             patch.object(copilot, 'coverage_answer', side_effect=AssertionError('Balance must not run')), \
             patch.object(copilot, 'answer_recorded_room_limit', side_effect=AssertionError('Sample facts must not run')):
            for question in ('Am I covered for cataract?', 'How much cover is left?', 'Investigate my claim deductions'):
                result = copilot.answer(question)
                self.assertEqual(result.answer.verdict, 'cant_confirm')
                self.assertEqual(result.answer.citations, [])
                self.assertEqual(result.answer.nextAction.route, '/upload')
                self.assertIn('sample policy', result.answer.summary)

    def test_example_child_can_still_use_sample_policy(self):
        token = session.set_session(session.new_session_id())
        self.addCleanup(session.reset_session, token)
        doc = {'status': 'ready', 'facts': {'insurer': 'Example'}, 'isDemoTemplate': True}
        with patch.object(policy_store, 'get_policy', return_value=doc):
            self.assertEqual(policy_store.get_active_policy_id(), 'demo-old-sample')
            self.assertEqual(policy_store.get_active_policy()[1]['facts']['insurer'], 'Example')
            self.assertFalse(policy_store.has_legacy_sample_policy())

    def test_private_upload_replaces_sample_and_clears_old_schedule(self):
        state = {'activePolicyId': 'demo-old-sample', 'policyDetails': {'sumInsured': 500000}}
        def save(update):
            state.update(update)
        with patch.object(policy_store, '_session_state', side_effect=lambda: dict(state)), \
             patch.object(policy_store, '_save_session_state', side_effect=save), \
             patch.object(policy_store, 'get_policy', return_value={'status': 'ready', 'facts': {'insurer': 'Uploaded insurer'}}):
            policy_store.set_active_policy('pol-private-upload')
            self.assertIs(state['policyDetails'], policy_store.firestore.DELETE_FIELD)
            state.pop('policyDetails')
            self.assertFalse(policy_store.has_legacy_sample_policy())
            self.assertEqual(policy_store.get_active_policy_id(), 'pol-private-upload')
            self.assertEqual(policy_store.get_active_policy()[1]['facts']['insurer'], 'Uploaded insurer')
