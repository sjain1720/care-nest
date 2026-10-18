"""Trust statuses must follow source checks and arithmetic, not generated claims."""
import json
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch

from app.schemas import Citation, PolicyFacts, WaitingPeriod
from app.services.answer_evidence import bound_dates, build_verification, matched_quote, prepare_dates, restrict_timing_answer, timing_facts_answer
from app.services import policy_qa
from app.services.answer_support import SupportReview

QUOTE = 'Listed cataract procedures require 24 months of continuous coverage.'
RULE = 'Expenses related to the treatment of the listed Conditions, surgeries/treatments shall be excluded until the expiry of 12 months of continuous coverage after the date of inception of the first policy with us.'
CONDITION = 'If any of the specified disease/procedure falls under the waiting period specified for pre -Existing diseases, then the longer of the two waiting periods shall apply.'
RULE_PAGE = '3. Specified disease/ procedure waiting period (Code – Excl02)\na) ' + RULE + '\nc) ' + CONDITION
LIST_PAGE = 'Policy wording · Page 19\ne) Prior continuous cover may reduce the waiting period.\nf) List of specific diseases/procedures\n(a) Cataract;\n(b) Benign Prostatic Hypertrophy;\n\nSpecific Exclusions\n4. Maternity Benefit Waiting Period'
QUESTION = 'For cataract surgery on 2025-09-12, has my specified disease waiting period ended? What else needs confirmation?'


def continued_rule():
    f = facts()
    f.startDate = '2024-03-12'
    f.waitingPeriods[0] = WaitingPeriod(id='specific',label='Specific disease waiting period',kind='specific',
        duration='12 months',startDate=f.startDate,endDate='1900-01-01',appliesTo='Untrusted extracted label',
        citation=Citation(page=18,clause='Waiting periods',quote=RULE))
    sources = [{'page':18,'label':'Policy wording (page 18)','text':RULE_PAGE,'originalPage':True},
               {'page':19,'label':'Policy wording (page 19)','text':LIST_PAGE,'originalPage':True}]
    return f, sources


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
             patch.object(policy_qa,'review_support',return_value=SupportReview(status='supported' if support else 'unsupported')):
            return policy_qa.answer_question(question,today=date(2026,10,17))

    def test_service_attaches_actual_checks_and_does_not_approve_coverage(self):
        answer=self.answer('Cataract surgery on 2026-09-12?').answer
        self.assertEqual(answer.verification.dates[0].endDate,'2027-03-12')
        self.assertIn('insurer confirms',answer.verification.qualification)

    def test_unsupported_answer_or_missing_dates_cannot_inherit_green_checks(self):
        answer=self.answer('Cataract surgery on 2026-09-12?',support=False).answer
        self.assertEqual(answer.verdict,'needs_checking')
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

    def test_failed_ai_interpretation_does_not_discard_independently_checked_timing(self):
        answer=self.answer('For cataract surgery on 2026-09-12, has my specified disease waiting period ended?',support=False).answer
        self.assertEqual(answer.verification.scope,'timing_only')
        self.assertEqual(answer.verification.dates[0].endDate,'2027-03-12')
        self.assertEqual(next(c.status for c in answer.verification.checks if c.kind=='support'),'not_run')
        self.assertEqual(next(c.status for c in answer.verification.checks if c.kind=='dates'),'passed')
        self.assertNotIn('is covered',answer.summary)
        self.assertTrue(answer.citations)

    def test_timing_fallback_does_not_infer_applicable_period_from_diagnosis(self):
        answer=self.answer('Does cataract surgery on 2026-09-12 qualify?',support=False).answer
        self.assertEqual(answer.verdict,'needs_checking')
        self.assertFalse(answer.verification.dates)

    def test_timing_fallback_does_not_trust_extracted_kind_without_source_anchor(self):
        from app.services.answer_evidence import timing_facts_answer
        f=facts();text='This unrelated benefit requires 24 months of continuous coverage.'
        f.waitingPeriods[0].citation.quote=text
        dates=prepare_dates('For surgery on 2026-09-12, has the specified disease waiting period ended?',f,hits(text),date(2026,10,17))
        self.assertTrue(dates['calculations'])
        self.assertIsNone(timing_facts_answer('Has the specified disease waiting period ended?',f,dates))

    def test_cross_page_list_is_linked_and_longer_period_stays_conditional(self):
        f,sources=continued_rule()
        dates=prepare_dates(QUESTION,f,sources,date(2026,10,17))
        card,selected=timing_facts_answer(QUESTION,f,dates)
        proof=build_verification(f,card.citations,sources,False,dates,selected,timing_only=True)
        self.assertEqual(proof.treatment.treatment,'Cataract')
        self.assertEqual({c.page for c in card.citations},{18,19})
        self.assertEqual(proof.dates[0].endDate,'2025-03-12')
        self.assertTrue(proof.dates[0].periodEnded)
        self.assertLess(len(card.summary.split()),65)
        self.assertIn('If this treatment also falls under',card.toConfirm[0])
        self.assertEqual(proof.treatment.conditionCitation.quote,CONDITION)
        self.assertEqual(next(c.status for c in proof.checks if c.kind=='support'),'not_run')
        self.assertNotEqual(card.verdict,'covered')

    def test_unrelated_benefit_or_unoriginal_list_cannot_link_a_treatment(self):
        f,sources=continued_rule()
        for replacement in (
            LIST_PAGE.replace('f) List of specific diseases/procedures','4. Day care benefits\nList of specific diseases/procedures'),
            LIST_PAGE.replace('List of specific diseases/procedures','List of day care treatments'),
        ):
            changed=[sources[0],dict(sources[1],text=replacement)]
            self.assertFalse(prepare_dates(QUESTION,f,changed,date(2026,10,17))['treatments'])
        changed=[sources[0],dict(sources[1],originalPage=False)]
        self.assertFalse(prepare_dates(QUESTION,f,changed,date(2026,10,17))['treatments'])

    def test_conditional_ambiguous_or_nonadjacent_entry_is_not_simplified(self):
        f,sources=continued_rule()
        for replacement in ('Cataract unless due to accident;', 'Cataract or glaucoma;', 'Not cataract;'):
            changed=[sources[0],dict(sources[1],text=LIST_PAGE.replace('Cataract;',replacement))]
            self.assertFalse(prepare_dates(QUESTION,f,changed,date(2026,10,17))['treatments'])
        self.assertFalse(prepare_dates(QUESTION,f,[sources[0],dict(sources[1],page=20)],date(2026,10,17))['treatments'])
        changed=[dict(sources[0],text=RULE_PAGE+'\n4. Other waiting period'),sources[1]]
        self.assertFalse(prepare_dates(QUESTION,f,changed,date(2026,10,17))['treatments'])

    def test_membership_requires_both_retained_quotes_and_matching_period(self):
        f,sources=continued_rule();dates=prepare_dates(QUESTION,f,sources,date(2026,10,17))
        card,selected=timing_facts_answer(QUESTION,f,dates)
        for citations,period in ((card.citations[:1],selected),(card.citations,'wrong-period')):
            proof=build_verification(f,citations,sources,False,dates,period,timing_only=True)
            self.assertIsNone(proof.treatment)
            self.assertFalse(any(c.kind=='treatment' for c in proof.checks))

    def test_failed_ai_review_service_retains_both_pages_and_scoped_links(self):
        f,sources=continued_rule();doc={'facts':f.model_dump()}
        ai=Mock();ai.models.generate_content.return_value=Mock(parsed=policy_qa.AnswerOut(
            verdict='needs_checking',headline='Period',summary='Unconfirmed interpretation.',
            citations=[policy_qa.CiteRef(ref='C1',quote=RULE)],toConfirm=[],waitingPeriodId='specific'))
        with patch.object(policy_qa.store,'get_active_policy',return_value=('owned-policy',doc)), \
             patch.object(policy_qa.store,'search_clauses',return_value=sources), \
             patch.object(policy_qa.store,'load_page',side_effect=lambda _,p: next((h['text'] for h in sources if h['page']==p),None)), \
             patch.object(policy_qa,'embed_texts',return_value=[[0.0]]), \
             patch.object(policy_qa,'gemini',return_value=ai), \
             patch.object(policy_qa,'review_support',return_value=SupportReview(status='unsupported')):
            card=policy_qa.answer_question(QUESTION,today=date(2026,10,17)).answer
        self.assertEqual(card.verification.treatment.treatment,'Cataract')
        self.assertEqual(card.verification.treatment.listCitation.docUrl,'/api/policy/document?policyId=owned-policy')
        self.assertTrue(all(c.docUrl.endswith('policyId=owned-policy') for c in card.citations))

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
             patch.object(policy_qa,'review_support') as support:
            answer=policy_qa.answer_question('What is the cataract waiting period?').answer
        self.assertEqual(ai.models.generate_content.call_count,2)
        support.assert_not_called()
        self.assertFalse(answer.citations)
        self.assertNotIn('passed',[c.status for c in answer.verification.checks])
