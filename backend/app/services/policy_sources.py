"""Expand retrieved chunks to bounded original pages, preserving adjacent sentences."""
import re
from app.services import policy_store
from app.services.grounding import normalize

MAX_SOURCE_CHARS = 10000


def source_window(text: str, retrieved: str) -> str:
    """Keep original contiguous text around the ranked hit, not always the page prefix."""
    at = text.find(retrieved.strip()) if retrieved.strip() else -1
    start = max(0, at - max(0, MAX_SOURCE_CHARS - len(retrieved)) // 2) if at >= 0 else 0
    start = min(start, max(0, len(text) - MAX_SOURCE_CHARS))
    return text[start:start + MAX_SOURCE_CHARS]


def page_sources(policy_id: str, hits: list[dict]) -> list[dict]:
    result=[];seen=set()
    for hit in hits:
        page=hit['page']
        if page in seen:continue
        seen.add(page)
        text=policy_store.load_page(policy_id,page)
        # Legacy documents without page text retain their exact retrieved excerpt.
        result.append({'page':page,'label':f'Policy wording (page {page})',
                       'text':source_window(text, hit['text']) if text else hit['text'][:MAX_SOURCE_CHARS],
                       'originalPage': bool(text)})
    return result


def named_benefit_sources(question: str, policy_id: str, hits: list[dict]) -> list[dict]:
    """Rare printed names can be poor vector matches: retain literal original-page hits.

    This bounded supplement is only for distinctive hyphenated benefit/rider names.
    It retrieves text, never establishes what that benefit covers or its limit.
    """
    if not re.search(r'\b(?:benefit|rider)\b', question, re.I):
        return hits
    terms = list(dict.fromkeys(re.findall(r'\b[a-z][a-z0-9]*[-\u2010-\u2014][a-z][a-z0-9-]*\b', question, re.I)))[:3]
    common = {'co pay', 'pre existing', 'room rent', 'sub limit', 'pre hospitalization', 'post hospitalization'}
    terms = [t for t in terms if normalize(t) not in common]
    if not terms:
        return hits
    separators = r'[-\s\u2010-\u2014]*'
    patterns = [re.compile(r'\b' + separators.join(re.escape(part) for part in re.split(r'[-\u2010-\u2014]', t)) + r'\b', re.I)
                for t in terms]
    originals = policy_store.load_pages(policy_id)
    ranked = []
    for page, text in sorted((p, t) for p, t in originals.items() if isinstance(p, int)):
        # Check words contiguously. Similar spelling or shared fragments are not matches.
        if not isinstance(page, int) or not 1 <= page <= 100 or not text:
            continue
        match = next((found for pattern in patterns if (found := pattern.search(text))), None)
        if match:
            # A benefit can occur in a schedule, contents, examples and unrelated
            # exceptions before its definition. Prefer the actual numbered heading.
            numbered = any(re.search(r'^\s*\d+(?:\.\d+){1,5}\.?\s*' + pattern.pattern + r'\s*:?\s*$', text, re.I | re.M)
                           for pattern in patterns)
            standalone = any(re.search(r'^\s*' + pattern.pattern + r'\s*:?\s*$', text, re.I | re.M)
                             for pattern in patterns)
            ranked.append((3 if numbered else 2 if standalone else 0, page, text, match.group()))
    result = []
    for priority, page, text, name in sorted(ranked, key=lambda item: (-item[0], item[1])):
        if len(result) >= 4:
            break
        if any(h['page'] == page for h in result):
            continue
        result.append({'page': page, 'label': f'Policy wording (page {page})',
            'text': source_window(text, name), 'originalPage': True})
        if priority == 3 and originals.get(page + 1) and page < 100 and len(result) < 4:
            # A named clause's conditions/list may continue on the next page.
            result.append({'page': page + 1, 'label': f'Policy wording (page {page + 1})',
                'text': originals[page + 1][:MAX_SOURCE_CHARS], 'originalPage': True})
    pages = {h['page'] for h in result}
    return (result + [h for h in hits if h['page'] not in pages])[:10] if result else hits
