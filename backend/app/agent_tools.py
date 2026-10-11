"""Tools the ADK agents call. Each reads already-checked data (policy facts, bill check, settlement, checklist).
ADK uses the docstrings to decide when to call each tool."""
from datetime import date

from app.schemas import PolicyFacts
from app.services import case_store, policy_store
from app.services.case_builder import ESCALATION, build_case
from app.services.embeddings import embed_texts
from app.services.waiting_periods import parse_date, status


def _active_policy() -> tuple[str, PolicyFacts] | None:
    policy_id = policy_store.get_active_policy_id()
    doc = policy_store.get_policy(policy_id) if policy_id else None
    if not doc or doc.get("status") != "ready":
        return None
    return policy_id, PolicyFacts.model_validate(doc["facts"])


def search_policy(question: str) -> dict:
    """Find the policy clauses most relevant to a question. Returns page, clause label and text for each."""
    active = _active_policy()
    if not active:
        return {"error": "No policy uploaded yet."}
    hits = policy_store.search_clauses(active[0], embed_texts([question], "RETRIEVAL_QUERY")[0], 5)
    return {"clauses": [{"page": h["page"], "clause": h["label"], "text": h["text"][:1200]} for h in hits]}


def waiting_period_status() -> dict:
    """Every waiting period in the policy with its end date and whether it is over today (computed, not guessed)."""
    active = _active_policy()
    if not active:
        return {"error": "No policy uploaded yet."}
    today = date.today()
    return {"today": today.isoformat(), "waitingPeriods": [
        {"label": w.label, "duration": w.duration, "endDate": w.endDate, "appliesTo": w.appliesTo,
         "page": w.citation.page, "clause": w.citation.clause, **status(parse_date(w.endDate), today)}
        for w in active[1].waitingPeriods]}


def policy_summary() -> dict:
    """Key facts: product type, insurer, plan, sum insured, members, room rent, co-pay, deductible and sub-limits."""
    active = _active_policy()
    if not active:
        return {"error": "No policy uploaded yet."}
    return active[1].model_dump(include={"productType", "insurer", "planName", "sumInsured", "startDate", "members",
                                         "roomRent", "coPay", "deductible", "subLimits"})


def bill_check_summary() -> dict:
    """The checked hospital bill: total, problems found (missing pages, arithmetic, room limit), the estimate of what may
    not be paid, and the charges that are possibly not payable or need clarification, with bill page numbers."""
    bill = case_store.get_case().get("bill")
    if not bill:
        return {"error": "No hospital bill uploaded yet."}
    flagged = [{"description": i["description"], "amount": i["amount"], "page": i.get("page"), "status": i["tag"], "note": i.get("note")}
               for i in bill["items"] if i["tag"] != "likely_payable"][:30]
    return {"hospital": bill["hospital"], "total": bill["total"], "checks": [c["message"] for c in bill.get("checks", [])],
            "estimate": bill.get("estimate"), "flaggedCharges": flagged}


def settlement_breakdown() -> dict:
    """The insurer's settlement: claimed, approved, and each deduction with the insurer's reason, our reading, the
    calculation, how well it is supported (supported / check / unknown) and questions to ask."""
    case = case_store.get_case()
    if case.get("rejection"):
        return {"rejected": True, "reason": case["rejection"].get("reason")}
    s = case.get("settlement")
    if not s:
        return {"error": "No settlement letter uploaded yet."}
    return {"claimed": s["claimedAmount"], "approved": s["approvedAmount"], "reconciliation": s.get("reconciliation"),
            "deductions": [{k: d[k] for k in ("label", "amount", "insurerReason", "ourReading", "trust", "calculation", "questions")}
                           for d in s["deductions"]]}


def document_checklist() -> dict:
    """The family's claim checklist: each document, whether it is collected, where to get it and why it is needed."""
    case = build_case(case_store.get_case())
    return {"stage": case["stage"], "items": [{k: i[k] for k in ("name", "status", "source", "why", "group")} for i in case["checklist"]]}


def escalation_steps() -> dict:
    """Where to escalate if the insurer doesn't resolve the issue: insurer grievance cell, IRDAI Bima Bharosa, Ombudsman."""
    return {"steps": ESCALATION, "note": "Deadlines change; check the current time limits on the official sites before filing."}
