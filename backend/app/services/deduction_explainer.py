"""Explains each settlement deduction: bill evidence from code, policy clauses from vector search, wording from Gemini,
and every quote verified in code."""
from google.genai import types
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.gcp import gemini
from app.schemas import POLICY_DOC_URL
from app.services import policy_store
from app.services.embeddings import embed_texts
from app.services.grounding import quote_in_text
from app.services.policy_details import format_inr as _rupees
from app.services.settlement_checks import bill_evidence, has_reason

CLAUSES_PER_DEDUCTION = 3


class ClauseQuote(BaseModel):
    ref: str
    quote: str


class DeductionReading(BaseModel):
    id: str
    ourReading: str
    citations: list[ClauseQuote]
    questions: list[str]


class Readings(BaseModel):
    deductions: list[DeductionReading]


PROMPT = """You are the Bill & Settlement Analyst in CareNest, helping an Indian family understand deductions in their
health-insurance settlement. For each deduction ([d1], [d2], ...) you get the insurer's stated reason, evidence our code found in the
hospital bill, and candidate policy clauses [C..].

For each deduction write:
- ourReading: at most 60 words of simple English. Say whether the policy wording and the bill evidence support the
  insurer's reason. If the insurer gave no reason, say so plainly and that the family can ask for an itemised explanation.
  Never call a deduction wrong or promise it will be reversed; point out what is unclear.
- citations: the clause refs that support your reading, each with a quote copied WORD FOR WORD (8-30 words). Empty if none fit.
- questions: 1-2 specific questions the family should ask the insurer or hospital."""


def explain_deductions(deductions: list[dict], bill: dict | None) -> list[dict]:
    """deductions: [{"id", "label", "amount", "insurerReason", "page"}] -> frontend Deduction dicts."""
    policy_id = policy_store.get_active_policy_id()
    blocks, candidates = [], {}
    for d in deductions:
        evidence, calculation = bill_evidence(d["amount"], bill)
        d["evidence"], d["calculation"] = evidence, calculation
        hits = []
        if policy_id and has_reason(d["insurerReason"]):
            query = f"{d['label']}. {d['insurerReason']}"
            hits = policy_store.search_clauses(policy_id, embed_texts([query], "RETRIEVAL_QUERY")[0], CLAUSES_PER_DEDUCTION)
        candidates[d["id"]] = {f"C{i}": h for i, h in enumerate(hits, 1)}
        clauses = "\n".join(f"[C{i}] Page {h['page']} · {h['label']}: {h['text'][:900]}" for i, h in enumerate(hits, 1)) or "(no clauses)"
        blocks.append(f"[{d['id']}] {d['label']} – {_rupees(d['amount'])}\nInsurer's reason: {d['insurerReason']}\n"
                      f"Bill evidence: {'; '.join(evidence + calculation) or 'none found'}\nClauses:\n{clauses}")

    response = gemini().models.generate_content(
        model=get_settings().gemini_model,
        contents=[PROMPT, "\n\n".join(blocks)],
        config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=Readings, temperature=0.1),
    )
    readings = response.parsed if isinstance(response.parsed, Readings) else Readings.model_validate_json(response.text)
    by_id = {r.id: r for r in readings.deductions}

    out = []
    for d in deductions:
        r = by_id.get(d["id"])
        citations = []
        for c in (r.citations if r else []):
            hit = candidates[d["id"]].get(c.ref.strip("[] "))
            if hit and quote_in_text(c.quote, hit["text"]):
                citations.append({"docId": "policy", "docName": "Policy wording", "page": hit["page"],
                                  "clause": hit["label"], "quote": c.quote, "docUrl": POLICY_DOC_URL})
        citations.append({"docId": d["docId"], "docName": "Settlement letter", "page": d["page"],
                          "clause": "Deductions", "quote": f"{d['label']}: {_rupees(d['amount'])}", "docUrl": d["docUrl"]})
        reasoned = has_reason(d["insurerReason"])
        supported = reasoned and (len(citations) > 1 or bool(d["calculation"]) or bool(d["evidence"]))
        out.append({
            "id": d["id"], "label": d["label"], "amount": d["amount"],
            "insurerReason": d["insurerReason"] if reasoned else "No reason or clause stated.",
            "ourReading": r.ourReading if r else "We could not analyse this deduction automatically.",
            "trust": "supported" if supported else ("check" if reasoned else "unknown"),
            "calculation": d["calculation"], "citations": citations, "evidence": d["evidence"],
            "questions": (r.questions if r else []) or (["Which bill items make up this amount, and which policy clause supports it?"]),
        })
    return out
