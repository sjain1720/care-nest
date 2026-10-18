"""Consequential document tasks must stay owned, current and distinct from uploading."""
import copy
import unittest
from io import BytesIO
from unittest.mock import patch
from fastapi import HTTPException, UploadFile
from app.schemas import DocumentTaskUpdate, UploadResult, TimelineEventIn
from app.services import claim_flow, case_store
from app.routers import policy, case as case_routes

KEY='a'*32

def fixture():
    return {'flowId':KEY,'documents':[{'id':'doc-owned','name':'report.pdf','type':'Other','pages':1}],
            'bill':{'total':1000,'reviewed':True,'hospital':'Sample hospital'},
            'timeline':[{'id':'ev-reply','kind':'reply','date':'2026-10-17','outcome':'asks_for_papers',
                         'reference':'REQUEST-123','papersAsked':['Discharge summary','Payment receipt']}]}

class ClaimFlowTests(unittest.TestCase):
    def setUp(self):
        self.case=fixture()
        def mutate(fn):
            self.case.update(fn(copy.deepcopy(self.case)))
            return copy.deepcopy(self.case)
        self.patches=[patch.object(case_store,'get_case',side_effect=lambda:copy.deepcopy(self.case)),
                      patch.object(case_store,'mutate_case',side_effect=mutate),
                      patch.object(claim_flow.policy_store,'get_active_policy',return_value=None)]
        for p in self.patches:p.start()
        self.addCleanup(lambda:[p.stop() for p in reversed(self.patches)])
    def reply_task(self):return next(t for t in claim_flow.task_list(self.case) if t['kind']=='reply')['id']
    def update(self,**kw):return claim_flow.update_task(self.reply_task(),DocumentTaskUpdate(claimKey=KEY,**kw))
    def test_other_owners_files_and_changed_claim_are_rejected(self):
        for body in (DocumentTaskUpdate(claimKey=KEY,documentIds=['doc-another-owner']),DocumentTaskUpdate(claimKey='b'*32,documentIds=['doc-owned'])):
            with self.assertRaises(claim_flow.FlowConflict):claim_flow.update_task(self.reply_task(),body)
        self.assertNotIn('documentTaskStates',self.case)
    def test_upload_link_is_not_review_and_review_requires_file(self):
        with self.assertRaises(claim_flow.FlowConflict):self.update(reviewed=True)
        claim_flow.link_uploaded(self.reply_task(),KEY,'doc-owned')
        self.assertFalse(next(t for t in claim_flow.task_list(self.case) if t['kind']=='reply')['reviewed'])
        draft=claim_flow.response_draft()
        self.assertIn('still pending',draft['body']);self.assertFalse(draft['evidenceIndex']);self.assertNotIn('are attached',draft['body'])
        self.update(documentIds=['doc-owned'],reviewed=True)
        draft=claim_flow.response_draft()
        self.assertIn('report.pdf',draft['body']);self.assertTrue(draft['evidenceIndex']);self.assertIn('Payment receipt',draft['body'])
        self.assertNotIn('claim_sent',[e['kind'] for e in self.case['timeline']])
    def test_new_reply_invalidates_task_ids_and_draft_fingerprint(self):
        old_id=self.reply_task();old=claim_flow.response_draft()['inputFingerprint']
        self.case['timeline'].append({'id':'ev-new','kind':'reply','date':'2026-10-18','outcome':'asks_for_papers','papersAsked':['New report']})
        with self.assertRaises(claim_flow.FlowConflict):claim_flow.update_task(old_id,DocumentTaskUpdate(claimKey=KEY))
        self.assertNotEqual(old,claim_flow.response_draft()['inputFingerprint'])
    def test_not_applicable_requires_explanation_and_is_user_reported(self):
        with self.assertRaises(claim_flow.FlowConflict):self.update(notApplicable=True)
        self.update(notApplicable=True,note='No receipt was issued; please confirm an alternative.')
        self.assertIn('My explanation',claim_flow.response_draft()['body'])
    def test_policy_edit_invalidates_response(self):
        first=claim_flow.response_draft()['inputFingerprint']
        with patch.object(claim_flow.policy_store,'get_active_policy',return_value=('p',{'facts':{'policyNumber':'Changed'}})):
            self.assertNotEqual(first,claim_flow.response_draft()['inputFingerprint'])
    def test_stale_response_cannot_be_recorded_as_sent(self):
        with self.assertRaises(HTTPException) as err:
            case_routes.add_timeline_event(TimelineEventIn(kind='letter_sent',date='2026-10-17',letterKind='document_response',claimKey=KEY,replyId='ev-reply',inputFingerprint='0'*64))
        self.assertEqual(err.exception.status_code,409);self.assertEqual(len(self.case['timeline']),1)
    def test_guarded_mutation_rejects_a_midflight_claim_switch(self):
        self.case['flowId']='b'*32
        with case_store.guard_flow(KEY):
            with self.assertRaises(claim_flow.FlowConflict):case_store.update_case({'bill':{'total':99}})
        self.assertEqual(self.case['bill']['total'],1000)
    def test_upload_preflight_blocks_replacing_current_bill_without_choice(self):
        f=UploadFile(filename='bill.pdf',file=BytesIO(b'%PDF-1.7 fake-for-preflight'))
        with patch.object(policy,'process_upload') as process:
            with self.assertRaises(HTTPException) as err:policy.upload_document(f,'Hospital bill',KEY,None,False)
        self.assertEqual(err.exception.status_code,409);process.assert_not_called()
    def test_stale_task_update_cannot_overwrite_newer_links(self):
        previous=claim_flow.view(self.case)['fingerprint']
        self.update(documentIds=['doc-owned'])
        with self.assertRaises(claim_flow.FlowConflict):
            claim_flow.update_task(self.reply_task(),DocumentTaskUpdate(claimKey=KEY,expectedFingerprint=previous,documentIds=[]))
        self.assertEqual(len(next(t for t in claim_flow.task_list(self.case) if t['kind']=='reply')['documents']),1)

    def test_recording_current_response_does_not_close_or_mark_paid(self):
        draft=claim_flow.response_draft()
        case_routes.add_timeline_event(TimelineEventIn(kind='letter_sent',date='2026-10-17',letterKind='document_response',
            claimKey=KEY,replyId=draft['replyId'],inputFingerprint=draft['inputFingerprint']))
        self.assertEqual(self.case['timeline'][-1]['kind'],'letter_sent')
        self.assertEqual(self.case['timeline'][-1]['replyId'],'ev-reply')
        self.assertNotIn('closed',[e['kind'] for e in self.case['timeline']])

    def test_upload_links_without_automatic_review(self):
        def processed(*args):
            self.case['documents'].append({'id':'doc-'+__import__('hashlib').sha256(b'%PDF-test').hexdigest()[:16],'name':'test.pdf','type':'Other','pages':1})
            return UploadResult(detectedType='Other',pages=1)
        with patch.object(policy,'process_upload',side_effect=processed):
            result=policy.upload_document(UploadFile(filename='test.pdf',file=BytesIO(b'%PDF-test')),'Other',KEY,self.reply_task(),False)
        self.assertTrue(result.documentId)
        self.assertFalse(next(t for t in claim_flow.task_list(self.case) if t['kind']=='reply')['reviewed'])

    def test_auto_policy_cannot_change_selection_via_requested_item_upload(self):
        from app.services import policy_ingest, ocr
        with patch.object(policy_ingest,'classify',return_value='Policy document'), patch.object(ocr,'ocr_first_page',return_value='Policy wording'), patch.object(policy,'process_upload') as process:
            with self.assertRaises(HTTPException) as err:
                policy.upload_document(UploadFile(filename='policy.pdf',file=BytesIO(b'%PDF-test')),'auto',KEY,self.reply_task(),False)
        self.assertEqual(err.exception.status_code,400);process.assert_not_called()
