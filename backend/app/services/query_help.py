"""Cashless query helper: explains an insurer/TPA query, lists the documents to send and drafts a reply."""
from google.genai import types
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.gcp import gemini
from app.schemas import Citation
from app.services import policy_store
from app.services.embeddings import embed_texts
from app.services.grounding import quote_in_text
from app.services.privacy import mask_all


class QueryDoc(BaseModel):
    name: str
    source: str
    why: str


class CiteRef(BaseModel):
    ref: str
    quote: str


class QueryHelpOut(BaseModel):
    queryType: str
    plainMeaning: str
    urgency: str
    documents: list[QueryDoc]
    draftReply: str
    timelineNote: str
    citations: list[CiteRef]


PROMPT = """An Indian family received this query from their health insurer or TPA during a cashless hospital admission.
Help them respond quickly. Use simple English.
- queryType: a short label, e.g. "Cashless pre-authorisation query".
- plainMeaning: at most 70 words. Explain what is being asked and why (e.g. checking a waiting period). Say clearly if
  the request is on hold rather than rejected.
- urgency: one sentence on how quickly to reply and what happens meanwhile.
- documents: one entry per document asked for, with where to get it (hospital desk, lab, earlier doctor) and why.
- draftReply: a short reply the family can give the hospital insurance desk. Keep unknown details as [placeholders].
- timelineNote: one sentence telling them to ask the TPA desk which time limit applies and to note when they sent the papers.
  Do not state specific regulatory deadlines.
- citations: policy clause refs [C1].. that explain why the insurer asks, each with a WORD FOR WORD quote (8-30 words).
Never promise approval. No medical advice."""


def explain_query(query_text: str) -> dict:
    steps = [{"agent": "Claim Copilot", "label": "Reading the insurer's query"}]
    hits = []
    policy_id = policy_store.get_active_policy_id()
    if policy_id:
        hits = policy_store.search_clauses(policy_id, embed_texts([query_text], "RETRIEVAL_QUERY")[0], 4)
        steps.append({"agent": "Policy Specialist", "label": f"Checking {len(hits)} related clauses in your policy"})
    clauses = "\n\n".join(f"[C{i}] Page {h['page']} · {h['label']}\n{h['text'][:1200]}" for i, h in enumerate(hits, 1)) or "(no policy uploaded)"

    response = gemini().models.generate_content(
        model=get_settings().gemini_model,
        contents=[PROMPT, f"QUERY\n{query_text}", f"POLICY CLAUSES\n{clauses}"],
        config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=QueryHelpOut, temperature=0.2),
    )
    out = response.parsed if isinstance(response.parsed, QueryHelpOut) else QueryHelpOut.model_validate_json(response.text)

    citations = []
    for c in out.citations:
        idx = c.ref.strip("[]C ")
        hit = hits[int(idx) - 1] if idx.isdigit() and 0 < int(idx) <= len(hits) else None
        if hit and quote_in_text(c.quote, hit["text"]):
            citations.append(Citation(page=hit["page"], clause=hit["label"], quote=c.quote).model_dump())
    steps.append({"agent": "Verifier", "label": f"Checked sources: {len(citations)} of {len(out.citations)} quotes found in your policy"})

    help_ = mask_all({**out.model_dump(exclude={"citations"}), "citations": citations})
    return {"steps": steps, "help": help_}
