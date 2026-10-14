"""Protect source readiness and monetary reconciliation before agent execution."""
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.services.dispute_inputs import prepare_dispute


def decision():
    return {'policyId': 'p', 'bill': {'reviewed': True}, 'documents': [{'type': 'Hospital bill'}],
            'settlement': {'claimedAmount': 246000, 'approvedAmount': 208000, 'deductions': [
                {'id': 'd1', 'amount': 21600, 'insurerReason': 'Room category'},
                {'id': 'd2', 'amount': 6900, 'insurerReason': 'Consumables'},
                {'id': 'd3', 'amount': 9500, 'insurerReason': 'Other deductions'}]}}


class DisputePreparationTests(unittest.TestCase):
    def test_empty_guest_gets_missing_inputs_not_a_decision(self):
        output = prepare_dispute({}, None)
        self.assertEqual(output.status, 'needs_inputs')
        self.assertEqual({x.code for x in output.missingInputs}, {'policy_missing', 'decision_missing'})
        self.assertIsNone(output.reconciliation)

    def test_reconciles_actual_amounts_and_preserves_unknown_reason(self):
        output = prepare_dispute(decision(), 'p')
        self.assertEqual(output.status, 'ready_for_review')
        self.assertEqual(output.reconciliation.decisionDifference, 38000)
        self.assertEqual(output.reconciliation.itemizedDeductions, 38000)
        self.assertTrue(output.reconciliation.arithmeticOk)
        self.assertEqual(output.deductionsWithoutReason, ['d3'])

    def test_unreviewed_bill_wrong_policy_and_conflicting_decision_block_review(self):
        case = decision(); case['bill']['reviewed'] = False; case['rejection'] = {'reason': 'Rejected'}
        output = prepare_dispute(case, 'different-policy')
        self.assertEqual(output.status, 'needs_inputs')
        self.assertEqual({x.code for x in output.missingInputs}, {'policy_link_unconfirmed', 'bill_unreviewed', 'decision_conflict'})

    def test_fractional_difference_is_preserved_not_rounded_away(self):
        case = decision(); case['settlement'].update(claimedAmount=100.30, approvedAmount=90)
        case['settlement']['deductions'] = [{'id': 'd', 'amount': 10.20}]
        result = prepare_dispute(case, 'p').reconciliation
        self.assertFalse(result.arithmeticOk); self.assertEqual(result.unexplainedGap, 0.10)

    def test_invalid_amounts_are_flagged_not_sent_to_calculation(self):
        for value in (None, -1, float('nan'), float('inf')):
            case = decision(); case['settlement']['approvedAmount'] = value
            output = prepare_dispute(case, 'p')
            self.assertIsNone(output.reconciliation)
            self.assertIn('amounts_invalid', {x.code for x in output.missingInputs})

    def test_rejection_without_bill_can_start_limited_wording_review(self):
        output = prepare_dispute({'policyId': 'p', 'rejection': {'reason': ''}}, 'p')
        self.assertEqual(output.status, 'ready_for_review')
        self.assertTrue(output.warnings)
        self.assertIsNone(output.reconciliation)

    def test_api_reads_current_guest_inputs_only(self):
        from app.core.session import new_session_id, expiry
        with patch('app.core.session_middleware.resolve_session', return_value=(new_session_id(), expiry())), \
             patch('app.services.dispute_inputs.case_store.get_case', return_value=decision()), \
             patch('app.services.dispute_inputs.policy_store.get_active_policy_id', return_value='p'):
            with TestClient(app) as client:
                response = client.get('/api/case/dispute/inputs')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['reconciliation']['decisionDifference'], 38000)
