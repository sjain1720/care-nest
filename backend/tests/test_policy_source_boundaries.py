import unittest
from unittest.mock import patch
from app.services.policy_sources import page_sources
from app.services.grounding import quote_in_text
from app.services.case_facts import build_case_facts
from app.services import policy_store
from tests.test_copilot_and_letters import demo_case_doc


class PolicySourceBoundaryTests(unittest.TestCase):
    def test_adjacent_chunks_use_one_original_page_and_no_inherited_heading(self):
        text='If the room rent exceeds the limit\nthen only a rateable proportion applies, except to medical implants.'
        hits=[{'page':17,'label':'Annexure II','text':text[:35]}, {'page':17,'label':'Annexure II','text':text[35:]}]
        with patch.object(policy_store,'load_page',return_value=text) as load:
            sources=page_sources('owned-policy',hits)
        self.assertEqual(len(sources),1);load.assert_called_once_with('owned-policy',17)
        self.assertTrue(quote_in_text('If the room rent exceeds the limit then only a rateable proportion applies',sources[0]['text']))
        self.assertNotIn('Annexure',sources[0]['label'])
        self.assertFalse(quote_in_text('Every implant deduction will be reversed',sources[0]['text']))

    def test_generated_interpretation_is_never_an_original_case_fact(self):
        case=demo_case_doc();case['settlement']['deductions'][0]['ourReading']='Invented interpretation which must never become source evidence.'
        facts=build_case_facts(case)
        self.assertFalse(any('Invented interpretation' in f['text'] for f in facts))
        self.assertFalse(any(f['source']['docId']=='policy' for f in facts))
        records=[f for f in facts if f['source']['docId']=='settlement']
        self.assertTrue(records)
        self.assertTrue(all(f['source']['docName']=='Extracted settlement record' for f in records))

    def test_case_source_reuse_rejects_stale_snapshot(self):
        from app.services.case_qa import reusable_case_pages
        case={'disputeInvestigation':{'scope':'old','review':{'rows':[{'citations':[{'docId':'policy','page':17}]}]}}}
        with patch('app.services.dispute_review.snapshot',return_value={'scope':'new'}),patch.object(policy_store,'load_page') as load:
            self.assertEqual(reusable_case_pages(case,'owned-policy','What about implants?'),[])
        load.assert_not_called()

    def test_case_source_reuse_reads_original_page_without_embedding(self):
        from app.services.case_qa import reusable_case_pages
        case={'disputeInvestigation':{'scope':'current','review':{'rows':[{'citations':[{'docId':'policy','page':17}]}]}}}
        with patch('app.services.dispute_review.snapshot',return_value={'scope':'current'}),patch.object(policy_store,'load_page',return_value='Original medical implants exception text') as load:
            rows=reusable_case_pages(case,'owned-policy','What about implants?')
        self.assertEqual(rows[0]['text'],'Original medical implants exception text')
        load.assert_called_once_with('owned-policy',17)

    def test_unknown_reason_request_does_not_invent_policy_rationale(self):
        from app.services.case_qa import unknown_reason_contact
        from app.services.steps import StepLog
        case={'settlement':{'claimedAmount':185000,'approvedAmount':165000,'deductions':[
            {'label':'Other deduction','amount':4800,'insurerReason':'No reason or clause stated.'}]}}
        result=unknown_reason_contact(case,'Who should I contact about the unexplained ₹4,800, and what exactly should I request?',StepLog(),'en')
        self.assertIn('₹4,800',result.answer.summary)
        self.assertEqual(result.answer.citations[0].docName,'Extracted settlement record')
        self.assertNotIn('implant',result.answer.summary)
        self.assertIsNone(unknown_reason_contact(case,'Who should I contact about unexplained ₹5,000?',StepLog(),'en'))
        self.assertIsNone(unknown_reason_contact(case,'Does the implant exception apply?',StepLog(),'en'))

    def test_implant_followup_reuses_current_finding_with_original_quotes(self):
        from app.services.case_qa import verified_implant_followup
        from app.services.steps import StepLog
        text='Medical implants shall be reimbursed based on actual amounts incurred.'
        case={'disputeInvestigation':{'scope':'same','review':{'rows':[{
            'label':'Implant reduction','assessment':'related_wording','explanation':'An exception may conflict with this reduction.',
            'citations':[{'page':17,'clause':'Policy wording','quote':text}], 'missingInformation':['Ask for the basis.']}]}}}
        with patch('app.services.dispute_review.snapshot',return_value={'scope':'same','policyId':'p'}),patch.object(policy_store,'load_page',return_value=text):
            answer=verified_implant_followup(case,'Does the room-rent reduction apply to the implant too?',StepLog(),'en')
        self.assertEqual(answer.answer.citations[0].docId,'policy')
        with patch('app.services.dispute_review.snapshot',return_value={'scope':'changed','policyId':'p'}):
            self.assertIsNone(verified_implant_followup(case,'Does the room-rent reduction apply to the implant too?',StepLog(),'en'))
