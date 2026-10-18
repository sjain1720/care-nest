"""A failed explanation review must not erase useful recorded claim facts."""
import unittest
from unittest.mock import Mock, patch

from app.services import case_qa


FACT = {
    'ref': 'F1',
    'text': 'Deduction "Other deductions" of ₹4,800. Insurer\'s reason: none stated.',
    'source': {'docId': 'settlement', 'docName': 'Extracted settlement record',
               'page': 2, 'clause': 'Extracted decision fields', 'docUrl': None},
}


class CaseAnswerFallbackTests(unittest.TestCase):
    def answer(self, quote, summary, support=True, verdict='needs_checking'):
        proposed = case_qa.CaseAnswerOut(verdict=verdict, headline='Proposed explanation',
            summary=summary, citations=[case_qa.CiteRef(ref='F1', quote=quote)],
            toConfirm=[], nextAction='letter')
        model = Mock()
        model.models.generate_content.return_value = Mock(parsed=proposed)
        with patch.object(case_qa.case_store, 'get_case', return_value={'settlement': {'claimedAmount': 10000}}), \
             patch.object(case_qa, 'build_case', return_value={'checklist': []}), \
             patch.object(case_qa, 'build_case_facts', return_value=[FACT]), \
             patch.object(case_qa, 'gemini', return_value=model), \
             patch.object(case_qa, 'check_support', return_value=support):
            return case_qa.answer_case_question('Why was the other deduction of ₹4,800 made?', 'settlement').answer

    def test_rejected_explanation_retains_matched_extracted_record(self):
        answer = self.answer(FACT['text'], 'The insurer must refund the ₹4,800.', support=False)
        self.assertEqual(answer.verdict, 'needs_checking')
        self.assertEqual(answer.citations[0].page, 2)
        self.assertIn('none stated', answer.summary)
        self.assertNotIn('must refund', answer.summary)
        self.assertIn('could not verify', answer.toConfirm[0])

    def test_bad_quote_recovers_relevant_fact_without_claiming_policy_proof(self):
        answer = self.answer('The insurer must refund ₹4,800.', 'The insurer must refund ₹4,800.')
        self.assertEqual(answer.verdict, 'needs_checking')
        self.assertEqual(answer.citations[0].docName, 'Extracted settlement record')
        self.assertIn('none stated', answer.summary)
        self.assertNotIn('must refund', answer.summary)

    def test_factual_extracted_amount_can_be_shown_without_a_policy_verdict(self):
        recovered = case_qa.related_case_fact('What is the other deduction amount?', [FACT], [])
        self.assertEqual(recovered[0].docName, 'Extracted settlement record')
        self.assertIn('₹4,800', recovered[1])

    def test_model_abstention_does_not_hide_a_matching_record(self):
        answer = self.answer('No matching quote', 'I cannot say anything.', verdict='cant_confirm')
        self.assertIn('₹4,800', answer.summary)
        self.assertNotIn('cannot say anything', answer.summary)


if __name__ == '__main__':
    unittest.main()
