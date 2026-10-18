import hashlib
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from app.services import deduction_trace as trace
ROOT=Path(__file__).resolve().parents[2]
class TraceTests(unittest.TestCase):
    def setUp(self):
        self.files={}
        self.case={'bill':{'reviewed':True,'items':[{'id':'b12','description':'Orthopaedic implant','category':'implants','amount':71925,'page':3}], 'roomRent':{'ratePerDay':2750}},'documents':[]}
        for name,kind in [('hospital_bill.pdf','Hospital bill'),('settlement_letter.pdf','Settlement letter')]:
            data=(ROOT/'demo-data'/name).read_bytes();identity='doc-'+hashlib.sha256(data).hexdigest()[:16]
            self.files[identity]=(data,'application/pdf');self.case['documents'].append({'id':identity,'type':kind})
        self.facts={'roomRent':{'amount':2500},'demoAssumptions':True}
        self.row=SimpleNamespace(label='Proportionate reduction on implant',amount=6100,evidence=None)
    def run_trace(self):
        with patch.object(trace.case_store,'load_file',side_effect=self.files.__getitem__):
            trace.attach_evidence(SimpleNamespace(rows=[self.row]),self.case,self.facts,'owned-current-scope')
        return self.row.evidence
    def test_originals_bind_discount_row_and_recorded_formula(self):
        result=self.run_trace();self.assertEqual(result['status'],'reconciles')
        self.assertEqual(result['calculation']['net'],'67100');self.assertEqual(result['calculation']['result'],'6100.00')
        self.assertEqual(result['billRows'][0]['id'],'b12');self.assertEqual([x['page'] for x in result['sources']],[3,2])
        self.assertEqual(result['inputFingerprint'],'owned-current-scope');self.assertTrue(all(len(x['docHash'])==64 for x in result['sources']))
    def test_changed_bill_or_selected_rate_does_not_reuse_recorded_inputs(self):
        self.case['bill']['items'][0]['amount']=72000;self.assertEqual(self.run_trace()['status'],'needs_inputs')
        self.case['bill']['items'][0]['amount']=71925;self.facts['roomRent']['amount']=3000
        self.assertEqual(self.run_trace()['status'],'needs_inputs')
    def test_missing_allocation_does_not_assume_global_discount_is_implant_only(self):
        result=trace.implant_trace(self.row,self.case,self.facts,'scope',[{'page':3,'text':'Hospital discount Rs. 4,825.00'}],[])
        self.assertEqual(result['status'],'needs_inputs');self.assertIsNone(result['calculation'])
    def test_mismatched_decision_is_not_a_refund(self):
        self.row.amount=6000;result=self.run_trace()
        self.assertEqual(result['status'],'mismatch');self.assertEqual(result['calculation']['difference'],'100.00')
        self.assertIn('does not establish policy applicability',result['qualification'])
