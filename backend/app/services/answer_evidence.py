"""Server-authored policy answer checks. A citation or model assertion cannot create a pass."""
import re
from datetime import date

from app.schemas import AnswerCheck, AnswerVerification, PolicyFacts, WaitingDateEvidence
from app.services.grounding import normalize
from app.services.waiting_periods import end_date, parse_date, status

_DURATION = re.compile(r'^(\d{1,3})\s+(days?|months?|years?)$', re.I)
_WAITING = re.compile(r'waiting|\bwait\b|cataract|\bafter\s+\d+\s+(?:months?|years?)', re.I)
_COMPARISON = re.compile(r'\b(?:today|now|yet|still|ended|elapsed)\b|\bafter\s+\d+\s+(?:months?|years?)|when.*(?:waiting|wait).*end', re.I)
# Deliberately accept only an explicitly named treatment/admission date, not a
# diagnosis, birth, renewal or otherwise unexplained date in the question.
_PLANNED_DATE = re.compile(
    r'\b(?:planned (?:admission|treatment|surgery) date\s*(?:is|:)?|'
    r'(?:admission|treatment|surgery|operation)\s+(?:(?:is\s+)?(?:planned|scheduled)\s+)?(?:on|for))\s*(\d{4}-\d{2}-\d{2})\b', re.I)


def matched_quote(quote: str, text: str) -> bool:
    """Contiguous words, allowing OCR whitespace/punctuation differences, no ellipsis stitching."""
    q = normalize(quote)
    return len(q.split()) >= 3 and not re.search(r'\.\.\.|…', quote) and q in normalize(text)


def waiting_question(question: str) -> bool:
    return bool(_WAITING.search(question) or _PLANNED_DATE.search(question))


def include_waiting_sources(question, facts, policy_id, hits, load_page):
    """Include cited waiting-rule pages and their continuation; bounded, no new AI call."""
    if not hits or not waiting_question(question):
        return hits
    result = list(hits)
    seen = {h['page'] for h in result}
    # Prefer actual rule pages over continuations if only a few slots remain.
    pages = [w.citation.page for w in facts.waitingPeriods]
    for page in dict.fromkeys(pages + [p + 1 for p in pages]):
        if len(result) >= 10:
            break
        if page in seen or not 1 <= page <= facts.pageCount:
            continue
        text = load_page(policy_id, page)
        if text:
            result.append({'page': page, 'label': f'Policy wording (page {page})',
                           'text': text[:10000], 'originalPage': True})
            seen.add(page)
    return result


def prepare_dates(question: str, facts: PolicyFacts, hits: list[dict], today: date) -> dict:
    """Calculate only from a source-matched duration and an explicitly named comparison date."""
    waiting = waiting_question(question)
    dates = set(_PLANNED_DATE.findall(question))
    comparison_requested = waiting and (bool(dates) or bool(_COMPARISON.search(question)))
    comparison = parse_date(next(iter(dates))) if len(dates) == 1 else None
    if not dates and re.search(r'\b(today|now|yet|still|ended)\b|when.*(?:waiting|wait).*end', question, re.I):
        comparison = today
    start = parse_date(facts.startDate)
    missing = []
    if comparison_requested:
        if not start:
            missing.append('Add the policy inception/continuous-cover start date in My policy.')
        if not comparison:
            missing.append('What is your planned treatment date? Use YYYY-MM-DD, for example “surgery on 2027-03-12”.')
        if start and comparison and comparison < start:
            missing.append('The treatment date is before the recorded policy start. Please check both dates.')
            comparison = None
    calculations = []
    if waiting and start and comparison and comparison_requested:
        pages = {h['page']: h for h in hits if h.get('originalPage') is True}
        for period in facts.waitingPeriods:
            duration = _DURATION.fullmatch(period.duration.strip())
            page = pages.get(period.citation.page)
            if not duration or not page or not matched_quote(period.citation.quote, page['text']):
                continue
            amount, unit = int(duration[1]), duration[2].lower().rstrip('s')
            if not 0 < amount <= 120:
                continue
            # A correct quote about 30 days must never validate an extracted 24-month period.
            if not re.search(rf'\b{amount}\s*\)?\s*{unit}s?\b', period.citation.quote, re.I):
                continue
            try:
                end = end_date(start, days=amount) if unit == 'day' else end_date(start, months=amount * (12 if unit == 'year' else 1))
            except (ValueError, OverflowError):
                continue
            checked = status(end, comparison)
            origin = ('Fictional example start date' if facts.demoAssumptions else
                      'User-entered start date; continuity not independently verified' if 'startDate' in facts.userProvided else
                      'Extracted policy start date; confirm continuity and member applicability')
            calculations.append(WaitingDateEvidence(periodId=period.id, label=period.label,
                duration=period.duration, startDate=start.isoformat(), startDateOrigin=origin,
                comparisonDate=comparison.isoformat(), endDate=end.isoformat(), periodEnded=checked['over'],
                daysRemaining=checked['daysLeft'], citation=period.citation))
    return {'waiting': waiting, 'requested': comparison_requested, 'calculations': calculations, 'missing': missing}


def bound_dates(citations, hits, dates, selected_period):
    pages = {h['page']: h for h in hits if h.get('originalPage') is True}
    if not citations or not all(c.page in pages and matched_quote(c.quote, pages[c.page]['text']) for c in citations):
        return []
    bound = []
    for calculation in dates['calculations']:
        if calculation.periodId != selected_period:
            continue
        n, unit = _DURATION.fullmatch(calculation.duration).groups()
        if any(c.page == calculation.citation.page and re.search(rf'\b{n}\s*\)?\s*{unit.rstrip("s")}s?\b', c.quote, re.I)
               for c in citations):
            bound.append(calculation)
    return bound


def restrict_timing_answer(answer, calculations, question):
    """Waiting-time evidence cannot mint a coverage verdict, even if a model labels it covered."""
    if not calculations:
        return
    answer.verdict = 'needs_checking' if re.search(r'\b(cover\w*|eligible|pay\w*|claim)\b', question, re.I) else 'info'
    if re.search(r'\b(covered|eligible|approved|paid)\b', answer.headline + ' ' + answer.summary, re.I):
        c = calculations[0]
        origin = ('fictional example' if c.startDateOrigin.startswith('Fictional') else 'recorded')
        answer.headline = 'Check the waiting period and other conditions'
        answer.summary = (f'Using the {origin} start date of {c.startDate}, the cited {c.duration} period ends on {c.endDate}. '
            f'By {c.comparisonDate}, this period ' + ('has ended. ' if c.periodEnded else 'has not ended. ')
            + 'This is a timing result; other applicable policy conditions still need checking.')
    if not re.search(r'\b(room|icu)\b', question, re.I):
        answer.toConfirm = [item for item in answer.toConfirm if not re.search(r'\b(room|differential billing|icu)\b', item, re.I)]
    answer.toConfirm = answer.toConfirm[:2]


def build_verification(facts, citations, hits, support, dates, selected_period=None):
    pages = {h['page']: h for h in hits if h.get('originalPage') is True}
    originals = bool(citations) and all(c.page in pages for c in citations)
    quotes = originals and all(matched_quote(c.quote, pages[c.page]['text']) for c in citations)
    checks = [
        AnswerCheck(kind='source', status='passed' if originals else 'not_confirmed',
            label='Policy page found' if originals else 'Policy evidence not confirmed',
            detail='The cited pages were read from the selected policy.' if originals else 'No original-page evidence was retained for this answer.'),
        AnswerCheck(kind='quote', status='passed' if quotes else 'not_confirmed',
            label='Quotation matched' if quotes else 'Quotation not confirmed',
            detail='Quoted words occur together on the cited pages; spacing and punctuation are normalized.' if quotes else 'A retrieved excerpt or a model-generated quote is not enough.'),
        AnswerCheck(kind='support', status='passed' if support is True and quotes else 'not_confirmed' if support is False else 'not_run',
            label='AI support review passed' if support is True and quotes else 'Explanation not verified',
            detail='An automated AI review checked the material statements against the supplied evidence. It can still make mistakes.' if support is True and quotes else 'The automated review did not establish support for this explanation.'),
    ]
    bound = bound_dates(citations, hits, dates, selected_period) if support is True and quotes else []
    if dates['waiting']:
        checks.append(AnswerCheck(kind='dates', status='passed' if bound else 'not_confirmed' if dates['requested'] else 'not_run',
            label='Dates compared in code' if bound else 'Dates still need checking' if dates['requested'] else 'Dates not compared',
            detail='Waiting-period end dates were recalculated from the source-matched duration and the recorded start date.' if bound else 'No verified date result is attached. Confirm the relevant waiting period, continuity/start date and planned treatment date.'))
    return AnswerVerification(policyId=facts.policyId, policyName=facts.planName, checks=checks, dates=bound,
        missingInputs=dates['missing'], qualification='Source matching, an automated support review and date arithmetic are separate checks. They do not establish that treatment is covered or a claim will be approved.')
