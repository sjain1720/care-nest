"""Source-only useful answers never reuse rejected prose or mint an AI-review pass."""
import json
from pathlib import Path
import unittest
from app.schemas import AnswerCard, Citation, PolicyFacts
from app.services.policy_fact_answer import source_fact_answer, basic_fact_sources, related_source_answer


class PolicyFactAnswerTests(unittest.TestCase):
    def setUp(self):
        raw=json.loads((Path(__file__).resolve().parents[2]/'frontend/public/mocks/policy.json').read_text())
        raw.update(policyId='owned-policy',planName='Test plan',sumInsured=1500000,demoAssumptions=[],userProvided=[])
        self.facts=PolicyFacts.model_validate(raw)
        self.room='Room Type Capping: Covered up to Sum Insured'
        self.hits=[self.hit(15,self.room),self.hit(3,'Policy Schedule\nBase Sum Insured (Rs.) 15,00,000'),self.hit(4,'Room Type Modification Not Opted')]
        self.answer=AnswerCard(verdict='covered',headline='Rejected',summary='Every room is unlimited and approved.',
            citations=[Citation(docId='policy',docName='Test plan',page=15,clause='Room',quote=self.room)],toConfirm=[])

    def hit(self,page,text,original=True):
        return {'page':page,'text':text,'label':'Policy','originalPage':original}

    def test_room_answer_shows_fact_amount_and_selected_option(self):
        a=source_fact_answer('What is my room-rent limit?',self.facts,self.answer,self.hits)
        self.assertEqual(a.verdict,'info')
        self.assertIn('does not state a separate daily',a.summary)
        self.assertIn('15,00,000',a.summary)
        self.assertIn('not a per-day',a.summary)
        self.assertIn('not opted',a.summary)
        self.assertNotIn('unlimited',a.summary)
        self.assertNotIn('approved',a.summary)
        self.assertEqual([c.page for c in a.citations],[15,3,4])
        self.assertIsNone(a.verification)

    def test_amount_without_original_schedule_is_not_promoted(self):
        a=source_fact_answer('What is my room-rent limit?',self.facts,self.answer,[self.hits[0]])
        self.assertNotIn('15,00,000',a.summary)

    def test_sum_insured_answer_uses_explicit_base_label(self):
        a=source_fact_answer('What is my sum insured?',self.facts,self.answer,self.hits)
        self.assertIn('15,00,000',a.summary)
        self.assertIn('not a statement of the balance',a.summary)
        self.assertEqual(a.citations[0].page,3)

    def test_conflicting_schedules_do_not_get_a_numeric_answer(self):
        hits=self.hits+[self.hit(2,'Policy Schedule\nBase Sum Insured (Rs.) 10,00,000')]
        a=source_fact_answer('What is my sum insured?',self.facts,self.answer,hits)
        self.assertNotIn('15,00,000',a.summary)
        self.assertNotIn('Base sum insured:',a.headline)

    def test_schedule_continuation_with_plain_inr_is_supported(self):
        hits=[self.hits[0],self.hit(3,'Policy Number: PRIVATE\nPolicy Period: CURRENT\nPremium: RECORD\nBase Sum Insured INR 15,00,000')]
        a=source_fact_answer('What is my sum insured?',self.facts,self.answer,hits)
        self.assertIn('15,00,000',a.summary)

    def test_illustration_does_not_establish_personal_sum_insured(self):
        hits=[self.hits[0],self.hit(3,'Example Policy Schedule: Base Sum Insured INR 15,00,000')]
        a=source_fact_answer('What is my sum insured?',self.facts,self.answer,hits)
        self.assertNotIn('15,00,000',a.summary)

    def test_bonus_and_other_benefits_are_not_base_cover(self):
        hits=[self.hits[0],self.hit(3,'Policy Schedule\nBonus Sum Insured 15,00,000\nM-iracle 15,000')]
        a=source_fact_answer('What is my sum insured?',self.facts,self.answer,hits)
        self.assertNotIn('15,00,000',a.summary)

    def test_coverage_request_stays_qualified(self):
        a=source_fact_answer('Will any room I choose be covered?',self.facts,self.answer,self.hits)
        self.assertEqual(a.verdict,'needs_checking')
        self.assertNotIn('unlimited',a.summary)

    def test_missing_or_edited_quote_cannot_produce_factual_answer(self):
        self.assertIsNone(source_fact_answer('What is my room limit?',self.facts,self.answer,[self.hit(15,self.room,False)]))
        self.answer.citations[0].quote='Room charges are unlimited'
        self.assertIsNone(source_fact_answer('What is my room limit?',self.facts,self.answer,self.hits))

    def test_unavailable_review_still_shows_source_with_small_warning(self):
        a=source_fact_answer('What is my room limit?',self.facts,self.answer,self.hits,True)
        self.assertIn('covered up to sum insured',a.summary)
        self.assertIn('temporarily unavailable',a.toConfirm[0])

    def test_optional_page_read_failure_keeps_existing_evidence(self):
        def fail(*args):raise RuntimeError('Unavailable')
        result=basic_fact_sources('What is my room-rent limit?',self.facts,'owned-policy',self.hits,fail)
        self.assertEqual(result,self.hits)

    def test_schedule_lookup_is_bounded_and_other_questions_do_not_read_pages(self):
        calls=[]
        def load(policy,page):calls.append(page);return 'Policy schedule'
        basic_fact_sources('What is my room-rent limit?',self.facts,'owned-policy',[],load)
        self.assertLessEqual(len(calls),6)
        calls.clear()
        basic_fact_sources('Is dental treatment covered?',self.facts,'owned-policy',[],load)
        self.assertFalse(calls)

    def test_related_excerpt_never_turns_an_illustration_into_personal_cover(self):
        hits=[self.hit(3,'Example: Base Sum Insured ₹15,00,000')]
        self.assertIsNone(related_source_answer('What is my sum insured?',self.facts,hits))

    def test_related_excerpt_requires_original_page_and_question_overlap(self):
        original=[self.hit(7,'Emergency ambulance charges are payable up to the limit in the policy schedule.')]
        answer=related_source_answer('What about ambulance charges?',self.facts,original)
        self.assertEqual(answer.verdict,'info')
        self.assertIn('ambulance charges',answer.summary)
        self.assertEqual(answer.citations[0].page,7)
        self.assertIsNone(related_source_answer('What about ambulance charges?',self.facts,[self.hit(7,original[0]['text'],False)]))
        self.assertIsNone(related_source_answer('What about dental surgery?',self.facts,original))
