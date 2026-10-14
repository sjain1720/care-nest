"""Blank financial images must not become invented bills or decisions."""
import hashlib
import unittest
from unittest.mock import Mock, patch
from app.services import case_ingest
from app.services.doc_extract import BillOut, BillItemOut
from app.services.file_types import UnreadableDocumentError

DATA = b'\x89PNG\r\n\x1a\nsynthetic-fixture'


class ReadabilityTests(unittest.TestCase):
    def test_blank_image_rejected_before_model_or_storage(self):
        for kind in ('Hospital bill', 'Settlement letter', 'Rejection letter'):
            with self.subTest(kind=kind), \
                 patch.object(case_ingest.case_store, 'get_case', return_value={}), \
                 patch.object(case_ingest, 'ocr_first_page', return_value='  '), \
                 patch.object(case_ingest, 'extract_bill') as model, \
                 patch.object(case_ingest, 'extract_settlement') as decision, \
                 patch.object(case_ingest.case_store, 'save_file') as storage, \
                 patch.object(case_ingest.case_store, 'update_case') as update:
                with self.assertRaises(UnreadableDocumentError):
                    case_ingest.process_case_document(DATA, 'blank.png', kind, 'image/png')
                model.assert_not_called(); decision.assert_not_called()
                storage.assert_not_called(); update.assert_not_called()

    def test_auto_classification_text_reused_without_another_ocr_call(self):
        with patch.object(case_ingest.case_store, 'get_case', return_value={}), \
             patch.object(case_ingest, 'ocr_first_page') as ocr:
            with self.assertRaises(UnreadableDocumentError):
                case_ingest.process_case_document(DATA, 'blank.png', 'Hospital bill', 'image/png', source_text='')
        ocr.assert_not_called()

    def test_validated_cached_image_does_not_pay_for_ocr_again(self):
        identity = 'img-' + hashlib.sha256(DATA).hexdigest()[:16]
        case = {'documents': [{'id': identity, 'type': 'Hospital bill', 'ocrReadable': True}], 'bill': {'total': 100}}
        with patch.object(case_ingest.case_store, 'get_case', return_value=case), \
             patch.object(case_ingest, 'ocr_first_page') as ocr, \
             patch.object(case_ingest, 'extract_bill') as model:
            result = case_ingest.process_case_document(DATA, 'bill.png', 'Hospital bill', 'image/png')
        self.assertTrue(result.reused); ocr.assert_not_called(); model.assert_not_called()

    def test_readable_image_extracts_and_marks_readability(self):
        extraction = BillOut(items=[BillItemOut(description='Room', category='room', amount=100, page=1)])
        with patch.object(case_ingest.case_store, 'get_case', return_value={}), \
             patch.object(case_ingest.policy_store, 'get_active_policy_id', return_value=None), \
             patch.object(case_ingest, 'ocr_first_page', return_value='Final bill Room 100'), \
             patch.object(case_ingest, 'extract_bill', return_value=extraction), \
             patch.object(case_ingest, '_limits', return_value=(None,None)), \
             patch.object(case_ingest.case_store, 'save_file'), \
             patch.object(case_ingest.case_store, 'update_case'), \
             patch.object(case_ingest.case_store, 'add_document') as add:
            result = case_ingest.process_case_document(DATA, 'bill.png', 'Hospital bill', 'image/png')
        self.assertEqual(result.detectedType, 'Hospital bill')
        self.assertTrue(add.call_args.args[0]['ocrReadable'])

    def test_no_bill_rows_cannot_be_saved_as_a_zero_rupee_bill(self):
        with patch.object(case_ingest.case_store, 'get_case', return_value={}), \
             patch.object(case_ingest, 'extract_bill', return_value=BillOut()), \
             patch.object(case_ingest.case_store, 'save_file') as storage:
            with self.assertRaises(UnreadableDocumentError):
                case_ingest.process_case_document(DATA, 'bill.png', 'Hospital bill', 'image/png', source_text='Unrelated text')
        storage.assert_not_called()
