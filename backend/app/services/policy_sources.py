"""Expand retrieved chunks to bounded original pages, preserving adjacent sentences."""
from app.services import policy_store


def page_sources(policy_id: str, hits: list[dict]) -> list[dict]:
    result=[];seen=set()
    for hit in hits:
        page=hit['page']
        if page in seen:continue
        seen.add(page)
        text=policy_store.load_page(policy_id,page)
        # Legacy documents without page text retain their exact retrieved excerpt.
        result.append({'page':page,'label':f'Policy wording (page {page})',
                       'text':(text or hit['text'])[:10000]})
    return result
