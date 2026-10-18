import unittest
from unittest.mock import Mock, patch
from app.services import bill_policy, conversation, copilot

class EvidenceTests(unittest.TestCase):
    def test_literal_room_context_retains_source_without_certifying_benefit_applicability(self):
        text='If the Insured Person incurs Room Rent higher than the eligible Room Rent in the Policy Schedule, only a rateable proportion applies.'
        rows=[{'id':'b1','category':'room','clauseRefs':['C1']}]
        for original in (True,False):
            results=[{'id':'b1','assessment':'needs_checking','citations':[]}]
            result=bill_policy.retain_room_wording(results,rows,{'C1':{'page':17,'label':'Room rent','text':text,'originalPage':original}},'p')[0]
            self.assertEqual(result['assessment'],'related_clause' if original else 'needs_checking')
            if original:
                self.assertEqual(result['basis'],'charge_type_wording')
                self.assertEqual(result['verificationIssues'],['benefit_applicability_pending'])
                self.assertNotIn('covered',result['explanation'])

    def setUp(self):
        self.text='Hospital room charges are payable subject to the room limit specified in the policy schedule.'
        self.rows=[{'id':'b1','amount':10000,'page':1,'clauseRefs':['C1']}]
        self.candidates={'C1':{'text':self.text,'page':7,'label':'Room rent'},'C2':{'text':self.text,'page':9,'label':'Other'}}
    def test_verified_quote_retains_bill_row_and_policy_page(self):
        out=bill_policy.Analysis(rows=[bill_policy.Row(id='b1',explanation='Fully covered!',citations=[bill_policy.Quote(ref='C1',quote=self.text)],missingInformation=['Check schedule.'])])
        row=bill_policy.verify_rows(out,self.rows,self.candidates)[0]
        self.assertEqual((row['billPage'],row['citations'][0]['page']),(1,7))
        self.assertEqual(row['assessment'],'related_clause')
        self.assertNotIn('Fully covered',row['explanation'])
    def test_wrong_ref_and_fabricated_quote_are_not_evidence(self):
        for ref,quote in [('C2',self.text),('C1','This invented sentence does not occur in the actual policy wording.')]:
            out=bill_policy.Analysis(rows=[bill_policy.Row(id='b1',explanation='Covered',citations=[bill_policy.Quote(ref=ref,quote=quote)],missingInformation=[])])
            row=bill_policy.verify_rows(out,self.rows,self.candidates)[0]
            self.assertEqual(row['assessment'],'needs_checking');self.assertEqual(row['citations'],[])
    def test_review_required_before_model_call(self):
        with patch.object(bill_policy.case_store,'get_case',return_value={'bill':{'reviewed':False}}), patch.object(bill_policy.policy_store,'get_active_policy',return_value=('p',{})), patch.object(bill_policy,'gemini') as model:
            with self.assertRaises(LookupError): bill_policy.analyse_bill_policy()
        model.assert_not_called()
    def test_cache_changes_when_schedule_or_row_changes(self):
        bill={'items':[{'amount':500}],'reviewed':True}
        a=bill_policy.fingerprint('p',{'roomRent':{'amount':5000}},bill)
        self.assertNotEqual(a,bill_policy.fingerprint('p',{'roomRent':{'amount':3000}},bill))
        self.assertNotEqual(a,bill_policy.fingerprint('other',{'roomRent':{'amount':5000}},bill))

class ConversationTests(unittest.TestCase):
    def test_policy_switch_discards_previous_turns(self):
        database=Mock();snap=database.collection.return_value.document.return_value.collection.return_value.document.return_value.get.return_value
        snap.exists=True;snap.to_dict.return_value={'scope':'old-policy','turns':[{'user':'Does my policy cover diabetes?'}]}
        with patch.object(conversation,'db',return_value=database), patch.object(conversation,'session_id',return_value='a'*32), patch.object(conversation,'scope_key',return_value='new-policy'), patch.object(conversation,'gemini') as model:
            question,context=conversation.prepare('What about that?', 'thread123')
        self.assertEqual(question,'What about that?');self.assertEqual(context['turns'],[]);model.assert_not_called()
    def test_followup_resolves_using_current_scoped_history(self):
        database=Mock();snap=database.collection.return_value.document.return_value.collection.return_value.document.return_value.get.return_value
        snap.exists=True;snap.to_dict.return_value={'scope':'same','turns':[{'user':'Does my policy cover diabetes?','assistant':'When was it diagnosed?'}]}
        model=Mock();model.models.generate_content.return_value=Mock(parsed=conversation.Resolved(question='Does my policy cover diabetes diagnosed last month?',followUp=True))
        with patch.object(conversation,'db',return_value=database), patch.object(conversation,'session_id',return_value='a'*32), patch.object(conversation,'scope_key',return_value='same'), patch.object(conversation,'gemini',return_value=model):
            question,_=conversation.prepare('It was diagnosed last month.', 'thread123')
        self.assertIn('diabetes',question);self.assertIn('last month',question);self.assertIn('It was diagnosed last month.',question)
    def test_promise_question_cannot_be_rewritten_into_coverage_answer(self):
        with patch.object(conversation,'scope_key') as scope:
            question,context=conversation.prepare('Is it definitely approved?', 'thread123')
        scope.assert_not_called();self.assertIsNone(context)

class QualityRegressionTests(unittest.TestCase):
    def test_medication_advice_is_refused_without_calling_model(self):
        with patch.object(copilot, 'route') as router:
            result = copilot.answer('Should I take antibiotics after my surgery?')
        router.assert_not_called()
        self.assertEqual(result.answer.verdict, 'cant_confirm')
        self.assertFalse(result.answer.citations)

class SemanticSupportTests(unittest.TestCase):
    def test_reviewer_must_support_all_claims(self):
        from app.services import answer_support
        model=Mock();model.models.generate_content.return_value=Mock(parsed=answer_support.SupportCheck(supported=True,unsupportedClaims=['Quote is unrelated.']))
        with patch.object(answer_support,'gemini',return_value=model):
            self.assertFalse(answer_support.check_support('Dental implant?',{'summary':'Covered'},'',[]))
    def test_review_failure_withholds_unverified_answer(self):
        from app.services import answer_support
        with patch.object(answer_support,'gemini',side_effect=RuntimeError('unavailable')):
            self.assertFalse(answer_support.check_support('Dental implant?',{},'',[]))

class ConstrainedBillOutputTests(unittest.TestCase):
    def test_each_required_bill_id_has_only_its_own_reference_choices(self):
        from pydantic import ValidationError
        schema=bill_policy.constrained_output([{'id':'b1','clauseRefs':['C1']},{'id':'b2','clauseRefs':['C2']}])
        valid={'b1':{'citations':[{'ref':'C1','quote':'Original room quote'}],'missingInformation':[]},
               'b2':{'citations':[],'missingInformation':[]}}
        self.assertEqual(schema.model_validate(valid).b1.citations[0].ref,'C1')
        valid['b1']['citations'][0]['ref']='C2'
        with self.assertRaises(ValidationError):schema.model_validate(valid)
        with self.assertRaises(ValidationError):schema.model_validate({'b2':valid['b2']})

    def test_exact_but_irrelevant_quote_is_withheld(self):
        rows=[{'id':'b1','description':'Consultant fees','assessment':'related_clause','citations':[{'page':20,'quote':'Blacklisted hospitals are excluded.'}]}]
        with patch.object(bill_policy,'check_rows',return_value=([{'id':'b1','supported':False,'unsupportedClaims':['No blacklisting evidence.']}],None)):
            result=bill_policy.check_relevance(rows,[{'id':'b1','description':'Consultant fees','category':'doctor','amount':100}],{})
        self.assertEqual(result[0]['assessment'],'needs_checking')
        self.assertEqual(result[0]['citations'],[])

    def test_broad_exclusion_cannot_become_specific_evidence_even_if_model_accepts(self):
        rows=[{'id':'b1','description':'Consultant fees','assessment':'related_clause','citations':[
            {'page':20,'quote':'Any Medical Practitioner specifically excluded by the Insurer and disclosed in its website'}]}]
        with patch.object(bill_policy,'check_rows') as model:
            result=bill_policy.check_relevance(rows,[{'id':'b1','description':'Consultant fees','category':'doctor','amount':100}],{})
        model.assert_not_called()
        self.assertEqual(result[0]['verificationIssues'],['applicability_condition_unconfirmed'])
        self.assertEqual(result[0]['citations'],[])
