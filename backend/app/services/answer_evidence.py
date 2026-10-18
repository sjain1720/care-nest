"""Server-authored policy answer checks. A citation or model assertion cannot create a pass."""
import re
from datetime import date

from app.schemas import AnswerCard, AnswerCheck, AnswerVerification, Citation, NextAction, PolicyFacts, WaitingDateEvidence, WaitingTreatmentEvidence
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
_SPECIFIC_HEADING = re.compile(r'(?:specified|specific)\s+disease\s*/\s*procedure\s+waiting\s+period[^\n]*', re.I)
_LIST_HEADING = re.compile(r'List\s+of\s+(?:specific|specified)\s+diseases\s*/\s*procedures', re.I)
_SECTION = re.compile(r'^\s*(?:\d{1,2}[.)]\s+[A-Z]|Specific Exclusions\b)', re.M | re.I)


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
    specific_ids = {w.id for w in facts.waitingPeriods if w.kind == 'specific'}
    treatments = [link for c in calculations if c.periodId in specific_ids
                  if (link := link_waiting_treatment(question, c, hits)) is not None]
    return {'waiting': waiting, 'requested': comparison_requested, 'calculations': calculations,
            'missing': missing, 'treatments': treatments}


def link_waiting_treatment(question, calculation, hits):
    """Literal list membership within the same waiting-rule section, never coverage.

    Conservative format support: a named rule followed by an explicit lettered list
    on that page or its immediate continuation. Unrecognized/conditional entries
    remain for interpretation; a mention in a separate benefit cannot qualify.
    """
    pages = {h['page']: h for h in hits if h.get('originalPage') is True}
    rule = pages.get(calculation.citation.page)
    if not rule or not matched_quote(calculation.citation.quote, rule['text']):
        return None
    headings = list(_SPECIFIC_HEADING.finditer(rule['text']))
    sections = []
    for heading in headings:
        tail = rule['text'][heading.end():]
        boundary = _SECTION.search(tail)
        body = tail[:boundary.start()] if boundary else tail
        if not matched_quote(calculation.citation.quote, body):
            continue
        sections.append((rule, body))
        if not boundary and rule['page'] + 1 in pages:
            continuation = pages[rule['page'] + 1]
            boundary = _SECTION.search(continuation['text'])
            sections.append((continuation, continuation['text'][:boundary.start()] if boundary else continuation['text']))
    links = []
    for page, text in sections:
        header = _LIST_HEADING.search(text)
        if not header:
            continue
        entries = list(re.finditer(r'\([a-z]\)\s*', text[header.end():], re.I))
        for i, entry in enumerate(entries):
            start = header.end() + entry.end()
            end = header.end() + entries[i + 1].start() if i + 1 < len(entries) else len(text)
            raw = text[start:end].strip()
            name = raw.rstrip('; .').strip()
            # Only simple, complete entries. Do not erase "unless", alternatives,
            # qualifiers, or infer synonyms/disease history from extracted metadata.
            if not re.fullmatch(r'[A-Za-z]+(?:[ -][A-Za-z]+){0,5}', name) or re.search(
                    r'\b(unless|except|and|or|not|following|subject|all|other)\b', name, re.I):
                continue
            named = re.search(r'\b' + re.escape(normalize(name)) + r'\b', normalize(question))
            if not named or re.search(r'\b(not|without|except)\s*$', normalize(question)[:named.start()]):
                continue
            quote = text[header.start():end].strip()
            if len(quote) > 1200 or not matched_quote(quote, page['text']):
                continue
            condition = None
            # Retain the full conditional sentence, not a generic PED assertion.
            condition_pattern = re.compile(r'If\s+any\s+of\s+the\s+specified\s+disease/procedure\s+falls\s+under[^.]{0,500}longer\s+of\s+the\s+two\s+waiting\s+periods\s+shall\s+apply\.', re.I)
            for source, section in sections:
                found = condition_pattern.search(section)
                if found and matched_quote(found.group(), source['text']):
                    condition = Citation(page=source['page'], clause='Longer waiting-period condition', quote=found.group())
                    break
            links.append(WaitingTreatmentEvidence(periodId=calculation.periodId, treatment=name,
                ruleCitation=calculation.citation.model_copy(),
                listCitation=Citation(page=page['page'], clause='Specified disease/procedure list', quote=quote),
                conditionCitation=condition))
    return links[0] if len(links) == 1 else None


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


def timing_facts_answer(question, facts, dates):
    """A narrow, explicitly named period can still yield checked facts if AI prose is withheld.

    This does not infer which procedure is covered, nor which period applies to a diagnosis.
    """
    if not dates['requested']:
        return None
    kind = ('specific' if re.search(r'\b(specified|specific)[- ](?:disease|illness|procedure)', question, re.I) else
            'ped' if re.search(r'\b(pre[- ]existing|PED)\b', question, re.I) else
            'initial' if re.search(r'\binitial waiting|\b30[- ]day', question, re.I) else None)
    ids = {w.id for w in facts.waitingPeriods if w.kind == kind}
    choices = [c for c in dates['calculations'] if c.periodId in ids]
    # The extracted kind alone cannot label a source passage as a specific/PED/initial rule.
    source_kind = {'specific': r'\b(?:specified|specific)\b|\blisted\s+(?:\w+\s+){0,3}(?:conditions|diseases|procedures)\b',
                   'ped': r'\bpre[- ]?existing\b|\bPED\b',
                   'initial': r'\bfirst policy\b|\bpolicy commencement\b|\binitial\b'}
    choices = [c for c in choices if kind and re.search(source_kind[kind], c.citation.quote, re.I)]
    if len(choices) != 1:
        return None
    c = choices[0]
    treatment = next((t for t in dates.get('treatments', []) if t.periodId == c.periodId), None)
    origin = 'fictional example' if facts.demoAssumptions else 'recorded'
    date_text = lambda value: date.fromisoformat(value).strftime('%d %b %Y').lstrip('0')
    outcome = 'had ended' if c.periodEnded else 'was still running'
    if treatment:
        summary = (f'For {treatment.treatment.lower()}, the cited {c.duration} period {outcome} by {date_text(c.comparisonDate)} '
            f'(rule: page {c.citation.page}; treatment listed: page {treatment.listCitation.page}). '
            f'Using the {origin} start of {date_text(c.startDate)}, it ends on {date_text(c.endDate)}.')
    else:
        summary = (f'The cited {c.duration} period {outcome} on {date_text(c.comparisonDate)}. '
            f'Using the {origin} start of {date_text(c.startDate)}, it ends on {date_text(c.endDate)}. '
            'Its applicability to this treatment still needs confirmation.')
    citations = [c.citation.model_copy()]
    confirm = ['Confirm continuous cover, member enrolment, any waiver and benefit limits in the issued schedule or certificate.']
    if treatment:
        citations.append(treatment.listCitation.model_copy())
        if treatment.conditionCitation:
            citations.append(treatment.conditionCitation.model_copy())
            confirm.insert(0, 'If this treatment also falls under the pre-existing-disease rule, the longer of the two periods applies. Confirm this using the condition’s onset/diagnosis history.')
    else:
        confirm.insert(0, 'Ask whether a different or longer waiting period applies to this treatment or the member’s medical history.')
    return AnswerCard(verdict='info', headline='Waiting period ended; coverage still needs checking' if c.periodEnded else 'Waiting period still running; check applicable conditions', summary=summary,
        citations=citations, toConfirm=confirm,
        nextAction=NextAction(label='Check policy details',route='/policy')), c.periodId


def build_verification(facts, citations, hits, support, dates, selected_period=None, timing_only=False, source_only=False):
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
    if timing_only:
        checks[-1] = AnswerCheck(kind='support',status='not_run',label='Coverage conditions to confirm',
            detail='Showing only the source-checked waiting-period wording and calendar result. A full coverage interpretation is not provided.')
    elif source_only:
        checks[-1] = AnswerCheck(kind='support', status='not_run' if support is None else 'not_confirmed',
            label='Answer check unavailable' if support is None else 'Interpretation not fully verified',
            detail='The automated explanation check could not run. The displayed quotations still match the original policy.' if support is None else
            'The proposed explanation did not pass the support review. The answer is limited to matched policy facts and quotations; applicability still needs checking.')
    bound = bound_dates(citations, hits, dates, selected_period) if (support is True or timing_only) and quotes else []
    treatment = next((t for t in dates.get('treatments', []) if t.periodId == selected_period
                      and bound and all(any(c.page == ref.page and normalize(c.quote) == normalize(ref.quote) for c in citations)
                                        for ref in (t.ruleCitation, t.listCitation))), None)
    if treatment:
        checks.append(AnswerCheck(kind='treatment',status='passed',label='Treatment listed',
            detail=f'{treatment.treatment} appears in the specified-disease/procedure list linked to this waiting rule. List membership alone does not establish coverage.'))
    if dates['waiting']:
        checks.append(AnswerCheck(kind='dates', status='passed' if bound else 'not_confirmed' if dates['requested'] else 'not_run',
            label='Dates compared in code' if bound else 'Dates still need checking' if dates['requested'] else 'Dates not compared',
            detail='Waiting-period end dates were recalculated from the source-matched duration and the recorded start date.' if bound else 'No verified date result is attached. Confirm the relevant waiting period, continuity/start date and planned treatment date.'))
    return AnswerVerification(policyId=facts.policyId, policyName=facts.planName, checks=checks, dates=bound,
        scope='timing_only' if timing_only else 'source_only' if source_only else 'explanation', missingInputs=dates['missing'], treatment=treatment,
        qualification='Timing only; confirm the applicable benefit and other conditions before relying on coverage.' if timing_only else
        'Check the attached clauses and issued schedule before acting. Source matching does not confirm personal eligibility or payment.' if source_only else
        'These checks support the explanation. Your insurer confirms coverage and payment.')
