"""Focused guards for the normal-chat investigation and its editable artifact."""
import unittest
from unittest.mock import patch
from app.services import claim_investigation as claim, dispute_review
from app.schemas import DisputeReview, DisputeReviewRow
from app.services.dispute_inputs import prepare_dispute


class InvestigationTests(unittest.TestCase):
    def test_routes_complex_turns_but_returns_simple_followups_to_python(self):
        self.assertTrue(claim.wants_investigation('Why was money deducted from my claim?'))
        self.assertTrue(claim.wants_investigation('Investigate my rejected claim and prepare an appeal'))
        self.assertFalse(claim.wants_investigation('Explain the room-rent clause you cited.'))
        self.assertFalse(claim.wants_investigation('What is a deduction in general?'))

    def test_paise_and_negative_reconciliation_gap_are_not_rounded_away(self):
        self.assertEqual(claim.money(38000.25), '₹38,000.25')
        self.assertEqual(claim.money(-0.5), '−₹0.50')

    def test_root_and_child_runners_share_a_model_budget(self):
        budget = {'modelCalls': 0, 'toolCalls': 0}
        root = dispute_review.build_team({'rows': [], 'scope': 'a'}, {}, budget, lambda *args: None)
        callbacks = [root.before_model_callback] + [tool.agent.before_model_callback for tool in root.tools]
        for i in range(8): callbacks[i % len(callbacks)](None, None)
        with self.assertRaises(RuntimeError): callbacks[-1](None, None)
        self.assertEqual(budget['modelCalls'], 8)

    def test_last_root_turn_cannot_spend_its_response_slot_on_more_tools(self):
        from types import SimpleNamespace
        from google.genai import types
        budget = {'modelCalls': 6, 'toolCalls': 0}
        root = dispute_review.build_team({'rows': [], 'scope': 'a'}, {}, budget, lambda *args: None)
        request = SimpleNamespace(config=types.GenerateContentConfig(), tools_dict={'optional': object()})
        root.before_model_callback(SimpleNamespace(agent_name='claim_copilot'), request)
        self.assertIsNone(request.config.tools)
        self.assertEqual(request.tools_dict, {})
        self.assertEqual(budget['modelCalls'], 7)

    def test_letter_uses_verified_questions_and_ignores_old_ai_readings(self):
        case = {'policyId': 'p', 'bill': {'reviewed': True}, 'documents': [],
                'settlement': {'claimedAmount': 10000.25, 'approvedAmount': 8000,
                    'deductions': [{'id': 'd1', 'amount': 2000.25, 'label': 'Other', 'trust': 'supported',
                        'ourReading': 'Guaranteed payment', 'insurerReason': 'Other deductions'}]}}
        review = DisputeReview(status='reviewed', preparation=prepare_dispute(case, 'p'), rows=[
            DisputeReviewRow(id='d1', label='Other', amount=2000.25, insurerReason='Other deductions',
                assessment='no_stated_reason', explanation='Unknown reason.', citations=[],
                missingInformation=['Please provide the itemized calculation and clause.'])])
        draft = claim.build_draft(review, case, {})
        self.assertIn('₹2,000.25', draft['body'])
        self.assertIn(review.rows[0].missingInformation[0], draft['body'])
        self.assertNotIn('Guaranteed payment', draft['body'])
        self.assertNotIn('are attached', draft['body'])

    def test_cached_letter_is_invalid_after_document_or_policy_change(self):
        artifact = {'scope': 'old', 'draft': {'kind': 'clarification', 'body': 'Old result'}}
        with patch.object(claim.case_store, 'get_case', return_value={'disputeInvestigation': artifact}), \
             patch.object(claim, 'snapshot', return_value={'scope': 'new'}):
            self.assertIsNone(claim.cached_draft('clarification'))
