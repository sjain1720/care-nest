"""Reads the whole policy with Gemini into structured facts, then verifies every quote and computes dates in code."""
from typing import Literal

from google.genai import types
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.gcp import gemini
from app.schemas import Citation, LimitFact, Member, PolicyFacts, PolicyFlag, PolicyTrap, WaitingPeriod
from app.services.grounding import locate_quote
from app.services.plain_language import STYLE
from app.services.policy_details import PRODUCT_NOTES
from app.services.waiting_periods import duration_label, end_date, parse_date


# ---------- what Gemini must return ----------

class Cite(BaseModel):
    page: int
    clause: str
    quote: str


class LimitOut(BaseModel):
    label: str
    amount: float | None = None
    unit: str | None = None
    citation: Cite | None = None


class MemberOut(BaseModel):
    name: str
    relation: str
    age: int | None = None


class WaitOut(BaseModel):
    label: str
    kind: Literal["initial", "specific", "ped"]
    months: int | None = None
    days: int | None = None
    appliesTo: str
    citation: Cite


class TrapOut(BaseModel):
    title: str
    explanation: str
    citation: Cite


class FlagOut(BaseModel):
    kind: Literal["missing_pages", "outdated", "ambiguous"]
    message: str
    citation: Cite | None = None


class PolicyExtraction(BaseModel):
    productType: Literal["health_indemnity", "travel", "hospital_cash", "critical_illness", "personal_accident", "other"] = "health_indemnity"
    isGroupPolicy: bool = False
    insurer: str | None = None
    planName: str | None = None
    policyNumber: str | None = None
    policyType: str | None = None
    sumInsured: float | None = None
    startDate: str | None = None
    renewalDate: str | None = None
    members: list[MemberOut] = []
    roomRent: LimitOut | None = None
    coPay: LimitOut | None = None
    deductible: LimitOut | None = None
    subLimits: list[LimitOut] = []
    waitingPeriods: list[WaitOut] = []
    traps: list[TrapOut] = []
    flags: list[FlagOut] = []


PROMPT = """You read Indian health-insurance policy documents for ordinary families.
The document text follows, split by markers like "=== Page 7 ===".

Extract the facts below. Rules:
- productType: "health_indemnity" if it pays hospital bills; "travel" for travel insurance; "hospital_cash" if it pays a
  fixed amount per day in hospital; "critical_illness" if it pays a lump sum on diagnosis; "personal_accident"; else "other".
  isGroupPolicy: true if it is issued to an employer/group/lender for its members.
- Many documents are policy WORDINGS without the personal schedule: start date, sum insured, members and policy number
  may be missing. Leave them null rather than using examples or tables from the wording.
- Use ONLY what the document says. If something is not stated, leave it null or empty. Never guess.
- Every citation: "page" is the number from the page marker; "clause" is the label as printed
  (e.g. "Clause 4.2", "Annexure II"), or "Page N" if there is none; "quote" is copied word for word
  from that page, 8 to 30 words.
- Amounts are plain numbers in rupees (500000, not "5 lakh"). Dates are YYYY-MM-DD.
- roomRent label: one plain sentence, e.g. "Up to ₹5,000 per day for a normal room (1% of sum insured)";
  amount = rupees per day for a normal room if it can be worked out from the document.
- coPay amount is the percentage. deductible amount is in rupees.
- waitingPeriods: give months or days exactly as written; do NOT calculate end dates.
  kind = "initial" (first 30 days etc.), "specific" (named illnesses), "ped" (pre-existing diseases).
- traps: the 3 to 5 rules most likely to reduce what the family is paid (room-rent proportionate
  deduction, co-pay, sub-limits, non-payable items, deadlines to inform the insurer). Explain each in
  one or two short sentences of simple English that a non-expert understands.
- flags: annexures or pages the document refers to but which are missing; dates that look outdated;
  wording that is unclear or could be read two ways. Explain in simple English.
- Write all labels and explanations in simple English. No legal jargon.""" + STYLE


def extract_policy_facts(pages: list[dict]) -> PolicyExtraction:
    text = "\n\n".join(f"=== Page {p['page']} ===\n{p['text']}" for p in pages)
    response = gemini().models.generate_content(
        model=get_settings().gemini_model,
        contents=[PROMPT, text],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=PolicyExtraction,
            temperature=0,
        ),
    )
    return response.parsed if isinstance(response.parsed, PolicyExtraction) else PolicyExtraction.model_validate_json(response.text)


# ---------- turn Gemini output into verified PolicyFacts ----------

def build_policy_facts(policy_id: str, ext: PolicyExtraction, pages: list[dict]) -> PolicyFacts:
    page_text = {p["page"]: p["text"] for p in pages}
    flags: list[PolicyFlag] = []

    def verify(cite: Cite, what: str) -> tuple[Citation, bool]:
        """Moves the citation to the page where the quote really is; flags it if the quote is nowhere."""
        found = locate_quote(cite.quote, page_text, cite.page)
        if found is None:
            flags.append(PolicyFlag(kind="ambiguous", message=f"We couldn't find the exact wording quoted for \"{what}\". Please check page {cite.page} yourself."))
        return Citation(page=found or cite.page, clause=cite.clause, quote=cite.quote), found is not None

    def limit(item: LimitOut | None, missing: str) -> LimitFact:
        if item is None:
            return LimitFact(label=missing)
        citation = verify(item.citation, item.label)[0] if item.citation else None
        return LimitFact(label=item.label, amount=item.amount, unit=item.unit, citation=citation)

    start = parse_date(ext.startDate)
    if start is None:
        flags.append(PolicyFlag(kind="ambiguous", code="missing_start_date",
                                message="We couldn't find the policy start date, so waiting-period end dates can't be worked out. Add it from your policy schedule."))
    renewal = parse_date(ext.renewalDate)

    waiting = []
    for i, w in enumerate(ext.waitingPeriods, 1):
        end = end_date(start, w.months, w.days) if start else None
        waiting.append(WaitingPeriod(
            id=f"wp-{i}", label=w.label, kind=w.kind, duration=duration_label(w.months, w.days),
            startDate=start.isoformat() if start else "", endDate=end.isoformat() if end else "",
            appliesTo=w.appliesTo, citation=verify(w.citation, w.label)[0],
        ))

    traps = []
    for t in ext.traps:
        citation, ok = verify(t.citation, t.title)
        traps.append(PolicyTrap(title=t.title, explanation=t.explanation, trust="supported" if ok else "check", citation=citation))

    doc_flags = [PolicyFlag(kind=f.kind, message=f.message, citation=verify(f.citation, f.message[:40])[0] if f.citation else None)
                 for f in ext.flags]

    return PolicyFacts(
        policyId=policy_id,
        insurer=ext.insurer or "Insurer not found in document",
        planName=ext.planName or "Your health policy",
        policyNumber=ext.policyNumber or "Not found",
        policyType=ext.policyType or "Not stated",
        sumInsured=ext.sumInsured or 0,
        startDate=start.isoformat() if start else "",
        renewalDate=renewal.isoformat() if renewal else "",
        pageCount=len(pages),
        members=[Member(name=m.name, relation=m.relation, age=m.age) for m in ext.members],
        roomRent=limit(ext.roomRent, "Room-rent limit not found in your document"),
        coPay=limit(ext.coPay, "No co-pay found in your document"),
        deductible=limit(ext.deductible, "No deductible found in your document"),
        subLimits=[limit(s, s.label) for s in ext.subLimits],
        waitingPeriods=waiting,
        traps=traps,
        flags=doc_flags + flags,
        productType=ext.productType,
        productNote=PRODUCT_NOTES.get(ext.productType),
        isGroupPolicy=ext.isGroupPolicy,
    )
