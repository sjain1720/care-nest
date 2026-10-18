"""Personal policy answers must recover supported rules without bypassing checks."""
import json
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import Mock, patch

from app.schemas import PolicyFacts
from app.services import policy_qa
from app.services import copilot
from app.services.answer_support import SupportCheck, SupportReview, review_support


QUOTE = 'Emergency ambulance charges are payable up to the limit specified in the policy schedule.'


def output(summary, ref='C1', quote=QUOTE):
    return policy_qa.AnswerOut(verdict='info', headline='Ambulance benefit', summary=summary,
        citations=[policy_qa.CiteRef(ref=ref, quote=quote)], toConfirm=['Check the limit in your issued schedule.'])


class UploadedPolicyAnswerTests(unittest.TestCase):
    def run_answer(self, outputs, reviews, original=True):
        raw = json.loads((Path(__file__).resolve().parents[2] / 'frontend/public/mocks/policy.json').read_text())
        raw.update(policyId='uploaded-private-policy', insurer='Test insurer', planName='Uploaded wording',
                   startDate='', waitingPeriods=[], userProvided=[], demoAssumptions=[])
        facts = PolicyFacts.model_validate(raw)
        model = Mock()
        model.models.generate_content.side_effect = [Mock(parsed=o) for o in outputs]
        with ExitStack() as stack:
            stack.enter_context(patch.object(policy_qa.store, 'get_active_policy', return_value=('uploaded-private-policy', {'facts': facts.model_dump()})))
            stack.enter_context(patch.object(policy_qa.store, 'search_clauses', return_value=[{'page': 2, 'text': QUOTE}]))
            stack.enter_context(patch.object(policy_qa.store, 'load_page', return_value=QUOTE if original else None))
            stack.enter_context(patch.object(policy_qa, 'embed_texts', return_value=[[0.0]]))
            stack.enter_context(patch.object(policy_qa, 'gemini', return_value=model))
            check = stack.enter_context(patch.object(policy_qa, 'review_support', side_effect=reviews))
            result = policy_qa.answer_question('What does my policy say about ambulance charges?')
        return result.answer, model.models.generate_content.call_count, check.call_count

    def test_rejected_extrapolation_is_corrected_once_and_independently_reviewed(self):
        answer, generated, checks = self.run_answer(
            [output('All your ambulance expenses are paid.'), output('Ambulance charges are subject to the limit in your schedule.')],
            [SupportReview(status='unsupported', unsupportedClaims=['No unlimited payment stated.']), SupportReview(status='supported')])
        self.assertEqual((generated, checks), (2, 2))
        self.assertEqual(answer.verification.scope, 'explanation')
        self.assertEqual(answer.verification.policyId, 'uploaded-private-policy')
        self.assertEqual(answer.citations[0].page, 2)
        self.assertIn('uploaded-private-policy', answer.citations[0].docUrl)
        self.assertNotIn('All your', answer.summary)
        self.assertEqual(next(c.status for c in answer.verification.checks if c.kind == 'support'), 'passed')

    def test_repeated_rejection_retains_only_matched_text_without_a_support_pass(self):
        answer, generated, checks = self.run_answer([output('Unlimited payment.'), output('Unlimited payment.')],
            [SupportReview(status='unsupported'), SupportReview(status='unsupported')])
        self.assertEqual((generated, checks), (2, 2))
        self.assertEqual(answer.verdict, 'info')
        self.assertEqual(answer.verification.scope, 'source_only')
        self.assertEqual(answer.citations[0].quote, QUOTE)
        self.assertNotIn('Unlimited', answer.summary)
        statuses = {c.kind: c.status for c in answer.verification.checks}
        self.assertEqual(statuses, {'source': 'passed', 'quote': 'passed', 'support': 'not_confirmed'})
        self.assertFalse(answer.verification.dates)

    def test_unavailable_review_is_not_reported_as_missing_policy_information(self):
        answer, generated, checks = self.run_answer([output('Schedule limit applies.')], [SupportReview(status='unavailable')])
        self.assertEqual((generated, checks), (1, 1))
        self.assertEqual(answer.verification.scope, 'source_only')
        self.assertIn('temporarily unavailable', ' '.join(answer.toConfirm))
        self.assertNotIn('not enough', answer.summary)
        self.assertTrue(answer.citations)
        support = next(c for c in answer.verification.checks if c.kind == 'support')
        self.assertEqual((support.status, support.label), ('not_run', 'Answer check unavailable'))

    def test_repair_cannot_invent_a_quote_or_gain_a_verification_pass(self):
        answer, generated, checks = self.run_answer(
            [output('Unlimited payment.'), output('Unlimited payment.', quote='All ambulance expenses are covered without limits.')],
            [SupportReview(status='unsupported')])
        self.assertEqual((generated, checks), (2, 1))
        self.assertEqual(answer.verification.scope, 'source_only')
        self.assertEqual(answer.citations[0].quote, QUOTE)
        self.assertNotIn('Unlimited', answer.summary)

    def test_source_repair_does_not_prevent_one_independently_checked_interpretation_repair(self):
        answer, generated, checks = self.run_answer(
            [output('Unverified.', ref='C99'), output('Unlimited payment.'), output('The schedule limit applies.')],
            [SupportReview(status='unsupported'), SupportReview(status='supported')])
        self.assertEqual((generated, checks), (3, 2))
        self.assertEqual(answer.verification.scope, 'explanation')

    def test_two_failed_corrections_are_bounded_and_never_earn_support_pass(self):
        answer, generated, checks = self.run_answer(
            [output('Unverified.', ref='C99'), output('Unlimited payment.'), output('Still unlimited payment.')],
            [SupportReview(status='unsupported'), SupportReview(status='unsupported')])
        self.assertEqual((generated, checks), (3, 2))
        self.assertEqual(answer.verification.scope, 'source_only')
        self.assertNotIn('unlimited', answer.summary.lower())

    def test_unoriginal_excerpt_never_becomes_source_only_evidence(self):
        answer, generated, checks = self.run_answer([output('Schedule limit applies.'), output('Schedule limit applies.')], [], original=False)
        self.assertEqual((generated, checks), (2, 0))
        self.assertFalse(answer.citations)
        self.assertNotIn('passed', [c.status for c in answer.verification.checks])

    def test_bad_model_quotations_still_show_relevant_original_wording(self):
        invalid = output('Unlimited ambulance payment.', quote='Unlimited ambulance payment without a limit.')
        answer, generated, checks = self.run_answer([invalid, invalid], [], original=True)
        self.assertEqual((generated, checks), (2, 0))
        self.assertEqual(answer.verification.scope, 'source_only')
        self.assertIn('Emergency ambulance charges', answer.summary)
        self.assertNotIn('Unlimited ambulance payment', answer.summary)
        self.assertIn('could not verify', answer.toConfirm[0])
        self.assertEqual(answer.citations[0].page, 2)
        self.assertEqual(next(c.status for c in answer.verification.checks if c.kind == 'support'), 'not_run')


class SupportDiagnosticTests(unittest.TestCase):
    def test_reviewer_rejection_reasons_remain_available_for_bounded_correction(self):
        model = Mock()
        model.models.generate_content.return_value = Mock(parsed=SupportCheck(supported=True, unsupportedClaims=['Unproven benefit.']))
        with patch('app.services.answer_support.gemini', return_value=model):
            review = review_support('A question', {}, '', [])
        self.assertEqual(review.status, 'unsupported')
        self.assertFalse(review.supported)
        self.assertEqual(review.unsupportedClaims, ['Unproven benefit.'])

    def test_service_error_has_distinct_unavailable_status_without_leaking_messages(self):
        with patch('app.services.answer_support.gemini', side_effect=RuntimeError('private data must not appear')):
            with self.assertLogs('app.services.answer_support', level='WARNING') as logs:
                review = review_support('A question', {}, '', [])
        self.assertEqual(review.status, 'unavailable')
        self.assertNotIn('private data must not appear', str(logs.output))


class SelectedPolicyRoutingTests(unittest.TestCase):
    def route_question(self, question, active=True, fail=False):
        model = Mock()
        if fail:
            model.models.generate_content.side_effect = RuntimeError('router unavailable')
        else:
            model.models.generate_content.return_value = Mock(parsed=copilot.Route(intent='policy', about='general'))
        with patch.object(copilot.policy_store, 'get_active_policy_id', return_value='uploaded-policy' if active else None), \
             patch.object(copilot, 'gemini', return_value=model):
            return copilot.route(question)

    def test_named_benefit_definition_uses_selected_policy_even_without_my(self):
        for fail in (False, True):
            self.assertEqual(self.route_question('what is the meaning of m-iracle benefit? what is it for?', fail=fail)[1], 'mine')

    def test_followup_limit_correction_stays_with_selected_policy(self):
        for question in ('but it says covered upto 15k? how does it means renewal of sum covered',
                         'That earlier explanation was wrong. What does this benefit actually mean?'):
            self.assertEqual(self.route_question(question)[1], 'mine')

    def test_explicit_general_request_and_no_policy_remain_general(self):
        self.assertEqual(self.route_question('In general, what is sum-insured restoration?')[1], 'general')
        self.assertEqual(self.route_question('What is a co-pay?', active=False)[1], 'general')


if __name__ == '__main__':
    unittest.main()
