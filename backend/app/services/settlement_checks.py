"""Deterministic checks on a settlement letter, matched against the bill. Pure Python."""
from app.services.policy_details import format_inr as _rupees

TOLERANCE = 2.0
_NO_REASON = {"", "-", "--", "na", "n/a", "nil", "none", "other", "others", "other deductions", "misc", "miscellaneous", "no reason or clause stated", "no clear reason stated", "no reason stated", "reason not provided", "not specified"}


def has_reason(reason: str | None) -> bool:
    return bool(reason) and reason.strip().strip('".').lower() not in _NO_REASON


def reconcile(claimed: float, approved: float, deductions: list[dict]) -> dict:
    total = sum(d["amount"] for d in deductions)
    gap = claimed - total - approved
    return {"deductedTotal": total, "arithmeticOk": abs(gap) <= TOLERANCE, "unexplainedGap": round(gap) if abs(gap) > TOLERANCE else 0}


def bill_evidence(amount: float, bill: dict | None) -> tuple[list[str], list[str]]:
    """(evidence lines, calculation lines) that explain a deduction amount from the bill, if any match."""
    if not bill:
        return [], []
    items = bill.get("items", [])
    evidence: list[str] = []
    calculation: list[str] = []

    exact = [i for i in items if abs(i["amount"] - amount) <= TOLERANCE]
    evidence += [f"Bill page {i.get('page', '?')}: \"{i['description']}\" – {_rupees(i['amount'])}" for i in exact[:2]]

    non_payable = [i for i in items if i.get("tag") == "possibly_non_payable"]
    if not exact and non_payable and abs(sum(i["amount"] for i in non_payable) - amount) <= TOLERANCE:
        evidence.append("Matches the total of the bill items on the non-payable list: "
                        + ", ".join(f"{i['description']} ({_rupees(i['amount'])})" for i in non_payable))

    room = bill.get("roomRent") or {}
    if room.get("overLimit"):
        for label, cut in (("doctor and nursing", room["narrowCut"]), ("doctor, nursing, surgery and anaesthesia", room["wideCut"])):
            if abs(room["roomCut"] + cut - amount) <= TOLERANCE:
                calculation = [
                    f"Room rent: {room['days']:g} days × ({_rupees(room['ratePerDay'])} − {_rupees(room['limitPerDay'])}) = {_rupees(room['roomCut'])}",
                    f"{label.capitalize()}: reduced to {room['eligibleShare']:.0%}, a cut of {_rupees(cut)}",
                    f"Total: {_rupees(room['roomCut'] + cut)} – matches this deduction",
                ]
                evidence.append(f"Bill: room at {_rupees(room['ratePerDay'])}/day against your {_rupees(room['limitPerDay'])}/day limit")
                break
    return evidence, calculation
