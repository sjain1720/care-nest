"""Useful source-only answers. Never reuse prose rejected by the support reviewer."""
import re
from app.schemas import AnswerCard, Citation, NextAction
from app.services.answer_evidence import matched_quote
from app.services.grounding import normalize
from app.services.policy_details import format_inr

ROOM = re.compile(r'\broom[ -]?(?:rent|limit|type|allowance)|\broom\b.*\b(?:limit|cap)\b', re.I)
SUM = re.compile(r'\b(?:sum (?:insured|assured)|base cover|total cover)\b', re.I)
_COMMON = {'about', 'after', 'before', 'could', 'does', 'from', 'have', 'into', 'mine',
           'policy', 'should', 'their', 'there', 'these', 'this', 'what', 'when', 'where',
           'which', 'would', 'your', 'covered', 'cover', 'claim', 'benefit'}


def basic_fact_sources(question, facts, policy_id, hits, load_page):
    """Check up to six schedule/known-room pages; no additional embedding/model call."""
    if not (ROOM.search(question) or SUM.search(question)):
        return hits
    pages = list(range(1, min(facts.pageCount, 5) + 1))
    if ROOM.search(question) and facts.roomRent.citation:
        pages.append(facts.roomRent.citation.page)
    result = list(hits)
    for page in dict.fromkeys(pages):
        if any(h['page'] == page and h.get('originalPage') for h in result):
            continue
        try:
            text = load_page(policy_id, page)
        except Exception:
            # Supplementary schedule lookup must not erase existing source evidence.
            continue
        if text and re.search(r'room[ -]?rent|room type (?:capping|modification)|base sum insured',text,re.I):
            result.append({'page':page,'label':f'Policy wording (page {page})','text':text[:10000],'originalPage':True})
    return result


def _sum_source(facts, hits):
    if facts.demoAssumptions or facts.sumInsured <= 0:
        return None
    # Only a labelled base amount in an issued schedule, never an example,
    # remaining balance, bonus or optional benefit with a similar number.
    found = []
    for h in hits:
        text = h['text']
        schedule = bool(re.search(r'policy\s*schedule|certificate\s+of\s+insurance', text, re.I)) or all(re.search(label, text, re.I) for label in (r'policy\s*number',r'policy\s*period',r'premium'))
        if not h.get('originalPage') or not schedule or re.search(r'\b(?:illustration|illustrative|example)\b',text,re.I):
            continue
        for match in re.finditer(r'\bBase\s+Sum\s+Insured\s*[:–-]?\s*(?:\(?(?:Rs\.?|INR|₹)\)?)?\s*[:₹-]?\s*([\d,]+(?:\.\d{1,2})?)\b', text, re.I):
            found.append((float(match[1].replace(',', '')), h, match[0]))
    if not found or {value for value, _, _ in found} != {facts.sumInsured}:
        return None
    _, h, quote = found[0]
    return Citation(docId='policy',docName=facts.planName,page=h['page'],clause='Issued base sum insured',quote=quote)


def related_source_answer(question, facts, hits, preferred_pages=()):
    """Show a relevant original-page excerpt when model quotation matching fails.

    This is extractive, not a coverage interpretation: page selection requires
    question-word overlap, and numeric base cover still needs the issued schedule.
    """
    if SUM.search(question) and not ROOM.search(question):
        amount = _sum_source(facts, hits)
        if not amount:
            return None
        return AnswerCard(verdict='info', headline=f'Base sum insured: {format_inr(facts.sumInsured)}',
            summary=f'Your issued schedule lists a base sum insured of {format_inr(facts.sumInsured)}. This is not the remaining claim balance.',
            citations=[amount], toConfirm=['Check the current policy year and any claims already paid before relying on the remaining balance.'],
            nextAction=NextAction(label='See policy details',route='/policy'))
    terms = {word.lower() for word in re.findall(r"[A-Za-z][A-Za-z0-9']{3,}", question.replace('-', ' '))
             if word.lower() not in _COMMON}
    if not terms:
        return None
    ranked = []
    for order, hit in enumerate(hits):
        if not hit.get('originalPage') or not hit.get('text'):
            continue
        text = hit['text']
        for term in terms:
            for match in list(re.finditer(r'\b' + re.escape(term) + r'\b', text, re.I))[:3]:
                start = max(0, match.start() - 90)
                end = min(len(text), match.end() + 210)
                if start:
                    start = text.find(' ', start, match.start()) + 1 or start
                if end < len(text):
                    last_space = text.rfind(' ', match.end(), end)
                    if last_space > match.end():
                        end = last_space
                quote = ' '.join(text[start:end].split())
                if not matched_quote(quote, text):
                    continue
                overlap = sum(bool(re.search(r'\b' + re.escape(word) + r'\b', quote, re.I)) for word in terms)
                if not overlap or (len(terms) > 1 and overlap < 2 and hit['page'] not in preferred_pages):
                    continue
                score = overlap * 10 + (3 if hit['page'] in preferred_pages else 0) - order
                if (re.search(r'\b(?:illustration|illustrative|example)\b', quote, re.I)
                        and not re.search(r'\b(?:illustration|illustrative|example)\b', question, re.I)):
                    continue
                ranked.append((score, -len(quote), hit, quote))
    if not ranked:
        return None
    _, _, hit, quote = max(ranked, key=lambda item: item[:2])
    citation = Citation(docId='policy', docName=facts.planName, page=hit['page'], clause=hit['label'], quote=quote)
    factual = bool(re.match(r'\s*(?:what|how much|explain|define|meaning)\b', question, re.I))
    return AnswerCard(verdict='info' if factual else 'needs_checking',
        headline='Relevant wording from your policy',
        summary=f'I found this on page {hit["page"]}: “{quote}”', citations=[citation],
        toConfirm=['I could not verify that this wording settles your specific question. Check the issued schedule and ask the insurer if applicability is unclear.'],
        nextAction=NextAction(label='See policy details',route='/policy'))


def source_fact_answer(question, facts, answer, hits, unavailable=False):
    citations = [c for c in answer.citations if any(h.get('originalPage') and h['page'] == c.page
        and matched_quote(c.quote, h['text']) for h in hits)]
    if not citations:
        return None
    warning = ('Answer review temporarily unavailable. ' if unavailable else 'Interpretation not fully verified. ') + 'Check the attached clauses and issued schedule before acting.'
    headline = 'What your policy says'
    summary = 'Your policy states: ' + ' '.join(f'“{c.quote}” (page {c.page}).' for c in citations[:2])
    factual = bool(re.match(r'\s*(?:what|how much|explain|define|meaning)\b',question,re.I))
    amount = _sum_source(facts, hits)
    if ROOM.search(question):
        # A literal entry can survive a failed broader eligibility interpretation.
        room = next((c for c in citations if 'room type capping covered up to sum insured' in normalize(c.quote)), None)
        if room:
            citations = [room]
            headline = 'Room benefit: up to sum insured'
            summary = ('Your policy lists room-type capping as “covered up to sum insured”. '
                'That entry does not state a separate daily rupee limit or establish a separate room-only allowance.')
            if amount:
                citations.append(amount)
                summary += f' Your issued base sum insured is {format_inr(facts.sumInsured)}; this is not a per-day room allowance.'
            # Optional modification wording must not silently become an applicable restriction.
            for h in hits:
                if not h.get('originalPage'):
                    continue
                match = re.search(r'Room\s+Type\s+Modification\s*[:–-]?\s*Not\s+Opted\b',h['text'],re.I)
                if match:
                    citations.append(Citation(docId='policy',docName=facts.planName,page=h['page'],clause='Selected room option',quote=match[0]))
                    summary += ' The schedule marks Room Type Modification as not opted.'
                    break
            warning = 'Confirm the eligible room category and applicable conditions in the attached policy pages before choosing a room.'
            if unavailable:
                warning = 'Answer review temporarily unavailable. ' + warning
    elif SUM.search(question) and factual and amount:
        citations = [amount]
        headline = f'Base sum insured: {format_inr(facts.sumInsured)}'
        summary = f'Your issued schedule lists a base sum insured of {format_inr(facts.sumInsured)}. This is the base cover, not a statement of the balance remaining after claims.'
    return answer.model_copy(update={'verdict':'info' if factual else 'needs_checking','headline':headline,
        'summary':summary,'citations':citations,'toConfirm':[warning]})
