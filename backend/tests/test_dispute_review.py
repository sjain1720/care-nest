"""ADK execution/state and mandatory source-verification regression checks."""
import json
import unittest
from unittest.mock import patch
from google.adk.agents import BaseAgent, SequentialAgent
from google.adk.events import Event, EventActions
from app.services import dispute_review as review
from app.services.dispute_inputs import prepare_dispute

TEXT = 'Room and boarding expenses are payable subject to the limit specified in the policy schedule.'


def bundle():
    return {'scope': 'original', 'rows': [{'id': 'd1', 'label': 'Room charges', 'amount': 2000,
        'insurerReason': 'Room limit exceeded', 'page': 1, 'docUrl': '/api/case/document/a'}],
        'sources': {'P1': {'page': 7, 'label': 'Room rent', 'text': TEXT}}, 'candidates': {'d1': ['P1']},
        'preparation': prepare_dispute({'policyId': 'p', 'bill': {'reviewed': True},
            'settlement': {'claimedAmount': 10000, 'approvedAmount': 8000, 'deductions': [{'amount': 2000}]}}, 'p').model_dump()}


def proposed():
    return review.SelectedEvidence(rows=[review.Selection(id='d1', clauseRefs=['P1'])]), \
        review.Readings(rows=[review.Reading(id='d1', explanation='Room expenses depend on the schedule limit; applicability needs confirmation.',
            citations=[review.Quote(ref='P1', quote=TEXT)], missingInformation=['Ask for the room eligibility used in the calculation.'])]), \
        review.Verification(rows=[review.Support(id='d1', supported=True, unsupportedClaims=[])])


class VerificationTests(unittest.TestCase):
    def test_exact_relevant_quote_is_related_wording_not_approval(self):
        row = review.verify_rows(bundle(), *proposed())[0]
        self.assertEqual(row.assessment, 'related_wording'); self.assertEqual(row.citations[0].page, 7)

    def test_wrong_row_reference_or_fabricated_quote_is_withheld(self):
        for wrong in ('ref', 'quote'):
            selected, readings, verification = proposed()
            if wrong == 'ref': readings.rows[0].citations[0].ref = 'P2'
            else: readings.rows[0].citations[0].quote = 'These made up words do not exist in the supplied policy wording.'
            row = review.verify_rows(bundle(), selected, readings, verification)[0]
            self.assertEqual(row.assessment, 'unverified'); self.assertFalse(row.citations)

    def test_semantically_unsupported_exact_quote_is_withheld(self):
        selected, readings, verification = proposed()
        verification.rows[0].unsupportedClaims = ['This clause does not establish the deduction applicability.']
        self.assertEqual(review.verify_rows(bundle(), selected, readings, verification)[0].assessment, 'unverified')

    def test_no_reason_is_not_inferred_by_agents(self):
        for reason in ('Other deductions', 'No reason or clause stated.', 'No clear reason stated.', None):
            with self.subTest(reason=reason):
                data = bundle(); data['rows'][0]['insurerReason'] = reason
                row = review.verify_rows(data, *proposed())[0]
                self.assertEqual(row.assessment, 'no_stated_reason'); self.assertFalse(row.citations)

    def test_related_wording_still_requests_applicability_calculation(self):
        selected, readings, verification = proposed(); readings.rows[0].missingInformation = []
        row = review.verify_rows(bundle(), selected, readings, verification)[0]
        self.assertEqual(row.assessment, 'related_wording')
        self.assertTrue(row.missingInformation)

    def test_missing_verifier_result_and_payment_promise_are_withheld(self):
        selected, readings, verification = proposed()
        verification.rows = []
        self.assertEqual(review.verify_rows(bundle(), selected, readings, verification)[0].assessment, 'unverified')
        _, _, verification = proposed(); readings.rows[0].explanation = 'This is definitely covered.'
        self.assertEqual(review.verify_rows(bundle(), selected, readings, verification)[0].assessment, 'unverified')

    def test_no_citation_cannot_release_unverified_interpretation(self):
        selected, readings, verification = proposed(); readings.rows[0].citations = []
        readings.rows[0].explanation = 'All room charges are payable.'
        row = review.verify_rows(bundle(), selected, readings, verification)[0]
        self.assertNotIn('All room charges', row.explanation)

    def test_duplicate_rows_rejected(self):
        selected, readings, verification = proposed(); readings.rows *= 2
        with self.assertRaises(ValueError): review.verify_rows(bundle(), selected, readings, verification)


class StateAgent(BaseAgent):
    updates: dict
    async def _run_async_impl(self, ctx):
        yield Event(author=self.name, actions=EventActions(state_delta=self.updates))


def scripted_team(data, evidence, budget, emit):
    evidence['sources'] = bundle()['sources']; evidence['candidates'] = bundle()['candidates']
    _, readings, _ = proposed()
    return StateAgent(name='claim_copilot', updates={'readings': readings.model_dump()})


class ExecutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_documents_do_not_call_agents(self):
        data = bundle(); data['preparation'] = prepare_dispute({}, None).model_dump()
        with patch.object(review, 'snapshot', return_value=data), patch.object(review, 'build_team') as agents:
            result = await review.run_review('Why was money cut?')
        self.assertEqual(result.status, 'needs_inputs'); agents.assert_not_called()

    async def test_actual_adk_runner_shares_structured_state_and_progress(self):
        with patch.object(review, 'snapshot', return_value=bundle()), \
             patch.object(review, 'session_id', return_value='a'*32), \
             patch.object(review, 'build_team', side_effect=scripted_team), \
             patch.object(review, 'check_rows', return_value=([{'id': 'd1', 'supported': True, 'unsupportedClaims': []}], None)):
            result = await review.run_review('Why was money cut?')
        self.assertEqual(result.status, 'reviewed')
        self.assertEqual(result.rows[0].assessment, 'related_wording')
        self.assertEqual([s.agent for s in result.steps], ['Document Inspector', 'Shared Verifier', 'Source Verifier'])

    async def test_policy_or_claim_change_discards_completed_result(self):
        changed = bundle(); changed['scope'] = 'different'
        with patch.object(review, 'snapshot', side_effect=[bundle(), changed]), \
             patch.object(review, 'session_id', return_value='a'*32), \
             patch.object(review, 'build_team', side_effect=scripted_team), \
             patch.object(review, 'check_rows', return_value=([{'id': 'd1', 'supported': True, 'unsupportedClaims': []}], None)):
            result = await review.run_review('Why was money cut?')
        self.assertEqual(result.status, 'stale'); self.assertFalse(result.rows)

class ApiTests(unittest.TestCase):
    def test_json_and_sse_retain_request_guest_context(self):
        from fastapi.testclient import TestClient
        from app.main import app
        from app.core.session import session_id, new_session_id, expiry
        from app.schemas import DisputeReview, AgentStep
        seen = []
        async def fake(question, on_step=None):
            seen.append(session_id())
            if on_step: on_step(AgentStep(agent='Document Inspector', label='Checked inputs'))
            return DisputeReview(status='needs_inputs', preparation=prepare_dispute({}, None))
        with patch('app.core.session_middleware.resolve_session', side_effect=lambda candidate: (candidate or new_session_id(), expiry())), \
             patch.object(review, 'run_review', side_effect=fake):
            with TestClient(app) as a, TestClient(app) as b:
                first = a.post('/api/case/dispute/review', json={'question': 'Why was money cut?'})
                streamed = b.post('/api/case/dispute/review/stream', json={'question': 'Why was money cut?'})
                self.assertEqual(first.status_code, 200); self.assertEqual(streamed.status_code, 200)
                self.assertEqual(seen, [a.cookies.get('cn_session'), b.cookies.get('cn_session')])
                self.assertNotEqual(seen[0], seen[1])
                self.assertIn('"type": "step"', streamed.text); self.assertIn('"type": "review"', streamed.text)
