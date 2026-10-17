"""Trust statuses must follow source checks and arithmetic, not generated claims."""
import json
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch

from app.schemas import Citation, PolicyFacts, WaitingPeriod
from app.services.answer_evidence import bound_dates, build_verification, matched_quote, prepare_dates, restrict_timing_answer
from app.services import policy_qa

QUOTE = 'Listed cataract procedures require 24 months of continuous coverage.'


def facts():
    # Synthetic facts exercise the example format, not the real Kotak duration.
    raw = json.loads((Path(__file__).resolve().parents[2] / 'frontend/public/mocks/policy.json').read_text())
    raw.update(policyId='owned-policy', startDate='2025-03-12', userProvided=['startDate'], demoAssumptions=[])
    raw['waitingPeriods'] = [WaitingPeriod(id='specific', label='Cataract waiting period', kind='specific',
        duration='24 months', startDate='2025-03-12', endDate='1900-01-01', appliesTo='Cataract',
        citation=Citation(page=12, clause='Waiting periods', quote=QUOTE)).model_dump()]
    return PolicyFacts.model_validate(raw)


def hits(text=QUOTE, original=True):
    return [{'page':12, 'label':'Waiting periods', 'text':text, 'originalPage':original}]


class AnswerEvidenceTests(unittest.TestCase):
    def test_computes_from_source_duration_not_cached_end_date(self):
        f = facts(); dates = prepare_dates('Cataract surgery on 2026-09-12?', f, hits(), date(2026, 10, 17))
        calc = dates['calculations'][0]
        self.assertEqual(calc.endDate, '2027-03-12')
        self.assertFalse(calc.periodEnded)
        proof = build_verification(f, [f.waitingPeriods[0].citation], hits(), True, dates, 'specific')
        self.assertTrue(all(c.status == 'passed' for c in proof.checks))
        self.assertIn('User-entered', proof.dates[0].startDateOrigin)

    def test_mismatched_duration_and_missing_original_cannot_earn_date_pass(self):
        for sources in (hits(QUOTE.replace('24 months','12 months')), hits(original=False)):
            dates = prepare_dates('Cataract surgery on 2026-09-12?', facts(), sources, date(2026, 10, 17))
            self.assertEqual(dates['calculations'], [])

    def test_onset_date_and_relative_months_do_not_invent_admission_date(self):
        for question in ('Does cataract cover apply after 18 months? Diagnosed on 2026-09-12.',
                         'Cataract surgery on 2026-02-30?'):
            dates = prepare_dates(question, facts(), hits(), date(2026, 10, 17))
            self.assertFalse(dates['calculations'])
            self.assertTrue(dates['missing'])

    def test_check_is_withheld_if_ai_review_fails_or_period_is_unbound(self):
        f=facts(); dates=prepare_dates('Cataract surgery on 2026-09-12?',f,hits(),date(2026,10,17))
        for support, selected in ((False,'specific'),(None,'specific'),(True,'invented-period')):
            proof=build_verification(f,[f.waitingPeriods[0].citation],hits(),support,dates,selected)
            self.assertFalse(proof.dates)
            self.assertNotEqual(next(c for c in proof.checks if c.kind=='dates').status,'passed')

    def test_quote_is_contiguous_and_missing_original_is_not_retained(self):
        self.assertTrue(matched_quote(QUOTE, QUOTE.replace('24 months','24\nmonths')))
        self.assertFalse(matched_quote('Listed cataract procedures ... continuous coverage', QUOTE))
        output=policy_qa.AnswerOut(verdict='partial',headline='Check waiting period',summary='Wait.',
            citations=[policy_qa.CiteRef(ref='C1',quote=QUOTE)],toConfirm=[])
        card,_=policy_qa.verify_answer(output,hits(original=False))
        self.assertFalse(card.citations)
        self.assertEqual(card.verdict,'cant_confirm')

    def answer(self, question, current=None, support=True):
        f=facts(); doc={'facts':f.model_dump()}
        ai=Mock();ai.models.generate_content.return_value=Mock(parsed=policy_qa.AnswerOut(
            verdict='needs_checking',headline='Cataract waiting period',summary='The waiting period has not ended.',
            citations=[policy_qa.CiteRef(ref='C1',quote=QUOTE)],toConfirm=[],waitingPeriodId='specific'))
        with patch.object(policy_qa.store,'get_active_policy',side_effect=[('owned-policy',doc),current or ('owned-policy',doc)]), \
             patch.object(policy_qa.store,'search_clauses',return_value=hits()), \
             patch.object(policy_qa.store,'load_page',side_effect=lambda _, p: QUOTE if p==12 else None), \
             patch.object(policy_qa,'embed_texts',return_value=[[0.0]]), \
             patch.object(policy_qa,'gemini',return_value=ai), \
             patch.object(policy_qa,'check_support',return_value=support):
            return policy_qa.answer_question(question,today=date(2026,10,17))

    def test_service_attaches_actual_checks_and_does_not_approve_coverage(self):
        answer=self.answer('Cataract surgery on 2026-09-12?').answer
        self.assertEqual(answer.verification.dates[0].endDate,'2027-03-12')
        self.assertIn('do not establish',answer.verification.qualification)

    def test_unsupported_answer_or_missing_dates_cannot_inherit_green_checks(self):
        answer=self.answer('Cataract surgery on 2026-09-12?',support=False).answer
        self.assertEqual(answer.verdict,'cant_confirm')
        self.assertFalse(answer.verification.dates)
        answer=self.answer('Cataract surgery after 18 months?').answer
        self.assertEqual(answer.verdict,'needs_checking')
        self.assertNotIn('has not ended',answer.summary)
        self.assertFalse(answer.verification.dates)

    def test_concurrent_policy_switch_discards_evidence_links(self):
        answer=self.answer('Cataract surgery on 2026-09-12?',current=('other-policy',{'facts':facts().model_dump()})).answer
        self.assertFalse(answer.citations)
        self.assertIsNone(answer.verification)
        self.assertIn('changed',answer.headline)

    def test_old_citation_link_cannot_open_replacement_policy(self):
        from fastapi import HTTPException
        from app.routers import policy
        with patch.object(policy,'_active_policy',return_value=('new-policy',{})), patch.object(policy.store,'load_original') as load:
            with self.assertRaises(HTTPException) as err:
                policy.get_policy_document(policyId='old-policy')
        self.assertEqual(err.exception.status_code,409)
        load.assert_not_called()

    def test_distinct_conditions_on_same_page_are_preserved(self):
        second='A longer pre-existing disease waiting period may also apply.'
        output=policy_qa.AnswerOut(verdict='needs_checking',headline='Conditions apply',summary='Check both periods.',
            citations=[policy_qa.CiteRef(ref='C1',quote=QUOTE),policy_qa.CiteRef(ref='C1',quote=second)],toConfirm=[])
        answer,_=policy_qa.verify_answer(output,hits(QUOTE+' '+second))
        self.assertEqual(len(answer.citations),2)

    def test_waiting_period_completion_never_creates_coverage_approval(self):
        from app.schemas import AnswerCard
        f=facts();dates=prepare_dates('Cataract surgery on 2028-09-12?',f,hits(),date(2026,10,17))
        card=AnswerCard(verdict='covered',headline='Covered',summary='Your cataract surgery is covered.',
            citations=[f.waitingPeriods[0].citation],toConfirm=['Confirm medical history.','Ask about room rent.'])
        restrict_timing_answer(card,bound_dates(card.citations,hits(),dates,'specific'),'Is cataract surgery covered?')
        self.assertEqual(card.verdict,'needs_checking')
        self.assertNotIn('is covered',card.summary)
        self.assertNotIn('Ask about room rent.',card.toConfirm)

    def test_source_repair_is_bounded_and_still_checked(self):
        f=facts(); doc={'facts':f.model_dump()}
        invalid=policy_qa.AnswerOut(verdict='partial',headline='Period',summary='Unverified.',
            citations=[policy_qa.CiteRef(ref='C99',quote='Invented source quotation for cataract treatment.')],toConfirm=[])
        ai=Mock();ai.models.generate_content.return_value=Mock(parsed=invalid)
        with patch.object(policy_qa.store,'get_active_policy',return_value=('owned-policy',doc)), \
             patch.object(policy_qa.store,'search_clauses',return_value=hits()), \
             patch.object(policy_qa.store,'load_page',side_effect=lambda _,p: QUOTE if p==12 else None), \
             patch.object(policy_qa,'embed_texts',return_value=[[0.0]]), \
             patch.object(policy_qa,'gemini',return_value=ai), \
             patch.object(policy_qa,'check_support') as support:
            answer=policy_qa.answer_question('What is the cataract waiting period?').answer
        self.assertEqual(ai.models.generate_content.call_count,2)
        support.assert_not_called()
        self.assertFalse(answer.citations)
        self.assertNotIn('passed',[c.status for c in answer.verification.checks])
