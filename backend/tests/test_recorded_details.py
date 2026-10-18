import json
from pathlib import Path
from datetime import datetime, timezone
import unittest
from unittest.mock import Mock, patch
from pydantic import ValidationError
from app.schemas import PolicyFacts, DisplayNameInput
from app.services import policy_qa, copilot, session_profile
from app.services.steps import StepLog
from app.core import session


class RecordedDetailsTests(unittest.TestCase):
    def facts(self, demo=True):
        value=json.loads((Path(__file__).resolve().parents[2]/'frontend/public/mocks/policy.json').read_text())
        value.update(userProvided=['roomRentPerDay'],roomRent={'label':'Selected normal room','amount':2500,'unit':'per day'},demoAssumptions=['Fictional example'] if demo else [])
        return PolicyFacts.model_validate(value)

    def test_room_selection_has_explicit_origin_and_needs_no_ai_or_embedding(self):
        for demo in (True,False):
            with self.subTest(demo=demo), patch.object(policy_qa.store,'get_active_policy',return_value=('selected',{'facts':self.facts(demo).model_dump()})), patch.object(policy_qa,'embed_texts',side_effect=AssertionError('Unexpected embedding')),patch.object(copilot,'route',side_effect=AssertionError('Unexpected model router')):
                result=copilot.answer('What is my room-rent limit?')
                self.assertEqual(result.answer.verdict,'info')
                self.assertIn('₹2,500',result.answer.summary)
                self.assertEqual(result.answer.citations,[])
                self.assertIn('fictional' if demo else 'entered',result.answer.summary)
                self.assertNotIn('Checked sources: 0',str(result.steps))

    def test_fast_path_cannot_answer_icu_or_claim_applicability(self):
        for question in ['What is my ICU room limit?','Will all charges be paid if my room is ₹2,500?','What is room rent in general?']:
            self.assertIsNone(policy_qa.recorded_room_limit(question,self.facts(),StepLog()))
        unknown=self.facts().model_copy(update={'userProvided':[]})
        self.assertIsNone(policy_qa.recorded_room_limit('What is my room-rent limit?',unknown,StepLog()))

    def test_demo_assumptions_are_not_described_as_issued_schedule(self):
        text=policy_qa._facts_block(self.facts(),datetime.now(timezone.utc).date())
        self.assertIn('NOT insurer-issued',text)
        self.assertNotIn('Entered by the user from their schedule',text)

    def test_profile_uses_root_owner_and_does_not_extend_retention(self):
        root,child=session.new_session_id(),session.new_session_id()
        tokens=session.set_session(child),session.set_root_session(root)
        database=Mock()
        database.collection.return_value.document.return_value.get.return_value.to_dict.return_value={'displayName':'Ananya'}
        try:
            with patch.object(session_profile,'db',return_value=database):
                self.assertEqual(session_profile.get_display_name(),'Ananya')
                session_profile.save_display_name('Ananya')
            database.collection.return_value.document.assert_called_with(root)
            database.collection.return_value.document.return_value.update.assert_called_once_with({'displayName':'Ananya'})
        finally:session.reset_root_session(tokens[1]);session.reset_session(tokens[0])

    def test_display_name_rejects_markup_blank_and_control_characters(self):
        for name in ['  ','<script>','A\nB','x'*61]:
            with self.assertRaises(ValidationError):DisplayNameInput(displayName=name)
        self.assertEqual(DisplayNameInput(displayName=' Ananya ').displayName,'Ananya')
