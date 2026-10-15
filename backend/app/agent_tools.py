"""Tools the ADK agents call. Each reads already-checked data (policy facts, bill check, settlement, checklist).
ADK uses the docstrings to decide when to call each tool."""
from datetime import date

from app.schemas import PolicyFacts
from app.services import case_store, policy_store
from app.services.case_builder import ESCALATION, build_case
from app.services.embeddings import embed_texts
from app.services.waiting_periods import parse_date, status
from app.services.dispute_inputs import prepare_dispute


def _active_policy() -> tuple[str, PolicyFacts] | None:
    active = policy_store.get_active_policy()
    return (active[0], PolicyFacts.model_validate(active[1]["facts"])) if active else None


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
    case = case_store.get_case()
    if case.get('policyId') != policy_store.get_active_policy_id():
        return {'error': 'The selected policy is not confirmed for this claim.'}
    bill = case.get('bill')
    if not bill:
        return {'error': 'No hospital bill uploaded yet.'}
    if bill.get('reviewed') is not True:
        return {'error': 'Review extracted bill rows and amounts before relying on them.'}
    return {'total': bill.get('total'), 'checks': [c['message'] for c in bill.get('checks', [])],
            'rows': [{k: item.get(k) for k in ('id', 'description', 'amount', 'page')}
                     for item in bill.get('items', [])[:40]],
            'note': 'Rows and arithmetic do not establish coverage. Generated tags/readings are not evidence.'}



def settlement_breakdown() -> dict:
    """Extracted insurer reasons and deterministic reconciliation, not AI trust labels or conclusions."""
    case = case_store.get_case()
    preparation = prepare_dispute(case, policy_store.get_active_policy_id())
    if preparation.status != 'ready_for_review':
        return {'error': 'Claim inputs need clarification.', 'preparation': preparation.model_dump()}
    if case.get('rejection'):
        return {'rejected': True, 'reason': case['rejection'].get('reason'),
                'page': case['rejection'].get('page'), 'preparation': preparation.model_dump()}
    settlement = case['settlement']
    return {'claimed': settlement['claimedAmount'], 'approved': settlement['approvedAmount'],
            'reconciliation': preparation.reconciliation.model_dump() if preparation.reconciliation else None,
            'deductions': [{k: d.get(k) for k in ('id', 'label', 'amount', 'insurerReason', 'page')}
                           for d in settlement['deductions']],
            'note': 'Insurer reasons are extracted text; check the original letter. Unknown reasons must not be inferred.'}



def document_checklist() -> dict:
    """The family's claim checklist: each document, whether it is collected, where to get it and why it is needed."""
    case = build_case(case_store.get_case())
    return {"basis": "Suggested preparation checklist; not verified insurer requirements", "stage": case["stage"], "items": [{k: i[k] for k in ("name", "status", "source", "why", "group")} for i in case["checklist"]]}


def escalation_steps() -> dict:
    """Where to escalate if the insurer doesn't resolve the issue: insurer grievance cell, IRDAI Bima Bharosa, Ombudsman."""
    return {"steps": ESCALATION, "note": "Deadlines change; check the current time limits on the official sites before filing."}
