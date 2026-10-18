"""Exercise API/service contracts that were lost when the UI branch was merged."""
import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from app.main import app
from app.services import copilot, policy_qa, case_qa
from app.services.general_qa import GeneralOut


class MergeIntegrationTests(unittest.TestCase):
    def setUp(self):
        from app.core.session import new_session_id, expiry
        patcher = patch("app.core.session_middleware.resolve_session", side_effect=lambda _: (new_session_id(), expiry()))
        patcher.start()
        self.addCleanup(patcher.stop)
        sample = patch.object(copilot.policy_store, 'has_legacy_sample_policy', return_value=False)
        sample.start()
        self.addCleanup(sample.stop)

    def test_json_and_streaming_routes_accept_language(self):
        with TestClient(app) as client:
            for path in ("/api/copilot/ask", "/api/copilot/ask/stream"):
                response = client.post(path, json={"question": "Will my claim definitely be approved?", "language": "hi"})
                self.assertEqual(response.status_code, 200)
                self.assertIn('cant_confirm', response.text)
                self.assertNotIn('Something went wrong', response.text)

    def test_general_question_without_policy_uses_general_answer(self):
        ai = Mock()
        ai.models.generate_content.return_value = Mock(parsed=GeneralOut(
            headline="Waiting periods", summary="Some benefits start after a waiting period.", toConfirm=["Check your policy."]))
        with patch.object(copilot, "route", return_value=("policy", "general", "router")), \
             patch.object(policy_qa.store, "get_active_policy", return_value=None), \
             patch("app.services.general_qa.gemini", return_value=ai):
            with TestClient(app) as client:
                response = client.post('/api/copilot/ask', json={"question": "What is a waiting period?", "language": "hi"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['answer']['general'])
        self.assertIn('Hindi', ai.models.generate_content.call_args.kwargs['contents'][0])

    def test_personal_question_without_policy_requests_upload(self):
        with patch.object(copilot, "route", return_value=("policy", "mine", "router")), \
             patch.object(policy_qa.store, "get_active_policy", return_value=None):
            response = copilot.answer("Does my policy cover maternity?", language="en")
        self.assertEqual(response.answer.verdict, "cant_confirm")
        self.assertEqual(response.answer.nextAction.route, "/upload")

    def test_policy_answer_uses_guest_schedule_and_language(self):
        facts = json.loads((Path(__file__).resolve().parents[2] / 'frontend/public/mocks/policy.json').read_text())
        facts.update(startDate='2025-06-01', userProvided=['startDate'])
        ai = Mock()
        ai.models.generate_content.return_value = Mock(parsed=policy_qa.AnswerOut(
            verdict='cant_confirm', headline='Check dates', summary='Check your schedule.', citations=[], toConfirm=[]))
        with patch.object(policy_qa.store, 'get_active_policy', return_value=('guest-policy', {'facts': facts})), \
             patch.object(policy_qa.store, 'get_policy') as raw_policy, \
             patch.object(policy_qa.store, 'search_clauses', return_value=[]) as search, \
             patch.object(policy_qa, 'embed_texts', return_value=[[0.0]*768]), \
             patch.object(policy_qa, 'gemini', return_value=ai):
            policy_qa.answer_question('When does my waiting period end?', language='hi')
        raw_policy.assert_not_called()
        self.assertEqual(search.call_args.args[0], 'guest-policy')
        contents = ai.models.generate_content.call_args.kwargs['contents']
        self.assertIn('2025-06-01', contents[1])
        self.assertIn('Hindi', contents[0])

    def test_unverified_summary_is_not_shown_as_fact(self):
        output = policy_qa.AnswerOut(verdict='covered', headline='Covered', summary='You receive a million rupees.', citations=[], toConfirm=[])
        card, _ = policy_qa.verify_answer(output, [])
        self.assertEqual(card.verdict, 'cant_confirm')
        self.assertNotIn('million', card.summary)

    def test_general_claim_question_does_not_require_a_bill(self):
        with patch.object(case_qa, 'general_answer') as general, patch.object(case_qa.case_store, 'get_case') as store:
            general.return_value = policy_qa.needs_policy().model_copy(update={'general': True})
            result = case_qa.answer_case_question('What is an itemised bill?', 'bill', about='general', language='hi')
        store.assert_not_called()
        self.assertTrue(result.answer.general)
        self.assertEqual(general.call_args.args[2], 'hi')
