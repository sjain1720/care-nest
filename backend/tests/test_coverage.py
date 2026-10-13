from datetime import date
import unittest
from unittest.mock import patch

from app.services.coverage import estimate_coverage, get_guest_coverage, policy_year
from app.schemas import CoverageEstimate

POLICY = {'policyId': 'policy-a', 'sumInsured': 500000, 'startDate': '2024-03-12', 'policyType': 'Family floater'}
TODAY = date(2026, 10, 14)


def claim(id='1', **changes):
    return {'id': id, 'title': 'Synthetic claim', 'policyId': 'policy-a', 'date': '2026-06-05',
            'approvedAmount': 42000, 'status': 'paid', 'claimNumber': id, **changes}


class CoverageTests(unittest.TestCase):
    def test_paid_only_current_policy_and_year(self):
        ledger = [claim('1', approvedAmount=208000), claim('2'), claim('old', date='2025-11-14'),
                  claim('pending', status='in_progress', approvedAmount=None), claim('other', policyId='policy-b'),
                  claim('unknown', policyId=None), claim('undated', date=''), claim('refused', status='refused', approvedAmount=0)]
        result = estimate_coverage(POLICY, ledger, TODAY)
        self.assertEqual((result['used'], result['remaining'], result['pct']), (250000, 250000, 50))
        self.assertEqual(result['year'], {'from': '2026-03-12', 'to': '2027-03-11'})
        self.assertEqual(len(result['counted']), 2)
        self.assertEqual(len(result['excluded']), 6)
        self.assertFalse(result['historyComplete'])
        CoverageEstimate.model_validate(result)

    def test_missing_schedule_never_shows_full_available_balance(self):
        for policy, expected in ((None, 'missing_policy'), ({**POLICY, 'sumInsured': 0}, 'missing_sum_insured'),
                                 ({**POLICY, 'startDate': ''}, 'missing_start_date'),
                                 ({**POLICY, 'startDate': '2026-02-30'}, 'missing_start_date'),
                                 ({**POLICY, 'startDate': '2027-01-01'}, 'not_started')):
            result = estimate_coverage(policy, [], TODAY)
            self.assertEqual(result['status'], expected)
            self.assertIsNone(result['remaining'])

    def test_decimal_amounts_and_duplicate_claim_numbers(self):
        p = {**POLICY, 'sumInsured': 100}
        result = estimate_coverage(p, [claim('1', approvedAmount=0.1), claim('2', approvedAmount=0.2),
                                      claim('duplicate', claimNumber='1', approvedAmount=99)], TODAY)
        self.assertEqual(result['used'], 0.3)
        self.assertEqual(result['remaining'], 99.7)
        self.assertEqual(result['excluded'][0]['reason'], 'duplicate_claim')

    def test_excess_payments_are_visible_and_remaining_not_negative(self):
        result = estimate_coverage(POLICY, [claim(approvedAmount=600000)], TODAY)
        self.assertEqual((result['used'], result['remaining']), (600000, 0))
        self.assertTrue(any('exceed' in warning for warning in result['warnings']))

    def test_invalid_money_is_excluded(self):
        result = estimate_coverage(POLICY, [claim(approvedAmount=float('nan'))], TODAY)
        self.assertEqual(result['used'], 0)
        self.assertEqual(result['excluded'][0]['reason'], 'invalid_amount')

    def test_anniversary_boundary_and_leap_start(self):
        self.assertEqual(policy_year(date(2024, 3, 12), date(2026, 3, 11)), (date(2025, 3, 12), date(2026, 3, 11)))
        self.assertEqual(policy_year(date(2024, 2, 29), date(2025, 2, 28)), (date(2025, 2, 28), date(2026, 2, 27)))

    def test_guest_endpoint_uses_server_selected_policy_and_ledger(self):
        with patch('app.services.policy_store.get_active_policy', return_value=('policy-a', {'facts': POLICY})), \
             patch('app.services.case_store.get_case', return_value={'policyId': 'policy-a', 'bill': {'total': 1000},
                   'billHeader': {'dischargeDate': '2026-06-05'}, 'settlement': {'approvedAmount': 500}}), \
             patch('app.services.case_store.list_past_claims', return_value=[]):
            result = get_guest_coverage()
        self.assertEqual(result['used'], 500)
        self.assertEqual(result['policyId'], 'policy-a')
