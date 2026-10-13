"""A guest's list of claims: one-line summaries of claims kept in CareNest and of past claims typed in by hand. Pure Python."""
import secrets

from app.services.claim_tracker import sorted_timeline

_CONTENT_KEYS = ("documents", "bill", "settlement", "rejection", "timeline", "checklistStatus")


def new_claim_id() -> str:
    return "cl-" + secrets.token_hex(4)


def has_content(case_doc: dict) -> bool:
    """False for a fresh claim with nothing uploaded, ticked or noted yet."""
    return any(case_doc.get(k) for k in _CONTENT_KEYS)


def claim_status(claimed: float | None, approved: float | None) -> str:
    if approved is None:
        return "in_progress"
    if approved <= 0:
        return "refused"
    if claimed and approved < claimed:
        return "part_paid"
    return "paid"


def summarize_case(case_doc: dict, claim_id: str) -> dict:
    header = case_doc.get("billHeader") or {}
    bill, settlement, rejection = (case_doc.get(k) or {} for k in ("bill", "settlement", "rejection"))
    timeline = sorted_timeline(case_doc.get("timeline"))
    approved = settlement.get("approvedAmount", 0) if settlement else (0 if rejection else None)
    # A later reply from the insurer can raise the amount paid.
    raised = [e["newApprovedAmount"] for e in timeline
              if e.get("kind") == "reply" and e.get("outcome") == "paid_more" and e.get("newApprovedAmount")]
    if raised:
        approved = raised[-1]
    claimed = settlement.get("claimedAmount") or bill.get("total") or None
    return {
        "id": claim_id,
        "source": "carenest",
        "policyId": case_doc.get("policyId"),
        "title": header.get("title") or header.get("diagnosis") or "Hospital claim",
        "patient": header.get("patientName") or "",
        "hospital": bill.get("hospital") or "",
        "date": header.get("dischargeDate") or header.get("admissionDate") or bill.get("billDate")
                or settlement.get("letterDate") or rejection.get("letterDate") or "",
        "claimNumber": settlement.get("claimNumber") or rejection.get("claimNumber") or "",
        "claimedAmount": claimed,
        "approvedAmount": approved,
        "status": claim_status(claimed, approved),
        "closed": bool(timeline) and timeline[-1].get("kind") == "closed",
    }


def manual_claim(entry: dict, claim_id: str) -> dict:
    """A claim the family made before (or outside) CareNest. It is already decided, so it counts as closed."""
    claimed, approved = entry.get("claimedAmount"), entry["approvedAmount"]
    return {
        "id": claim_id,
        "source": "manual",
        "policyId": entry.get("policyId"),
        "title": entry.get("title") or "Hospital claim",
        "patient": entry.get("patient") or "",
        "hospital": entry.get("hospital") or "",
        "date": entry["date"],
        "claimNumber": entry.get("claimNumber") or "",
        "claimedAmount": claimed,
        "approvedAmount": approved,
        "status": claim_status(claimed, approved),
        "closed": True,
    }


def newest_first(claims: list[dict]) -> list[dict]:
    return sorted(claims, key=lambda c: c.get("date") or "", reverse=True)
