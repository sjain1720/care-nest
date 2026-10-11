"""Merges details the user typed in (from their policy schedule) into the facts read from the policy wording.

Works on plain dicts so it needs no packages and is unit-tested locally.
"""
import copy
import re

from app.services.waiting_periods import end_date, parse_date

USER_DETAIL_FIELDS = ("startDate", "sumInsured", "members", "roomRentPerDay", "policyNumber")

PRODUCT_NOTES = {
    "health_indemnity": None,
    "travel": "This looks like a travel insurance policy. It covers medical emergencies while travelling, so hospital-bill checks for treatment in India may not apply.",
    "hospital_cash": "This looks like a hospital cash policy. It pays a fixed amount per day in hospital instead of paying your bills, so bill-by-bill checks don't apply.",
    "critical_illness": "This looks like a critical illness policy. It pays a lump sum when a listed illness is diagnosed, not your hospital bills.",
    "personal_accident": "This looks like a personal accident policy. It pays for accidental injury, disability or death, not regular hospital bills.",
    "other": "We couldn't tell what kind of policy this is. Check that it is a health insurance policy.",
}

_DURATION = re.compile(r"(\d+)\s*(month|day)", re.IGNORECASE)


def format_inr(amount: float) -> str:
    """500000 -> "₹5,00,000" (Indian digit grouping)."""
    digits = str(int(round(amount)))
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        head = ",".join([head[max(0, i - 2):i] for i in range(len(head), 0, -2)][::-1])
        digits = f"{head},{tail}"
    return f"₹{digits}"


def _recompute_waiting_periods(facts: dict, start_iso: str) -> None:
    start = parse_date(start_iso)
    for w in facts.get("waitingPeriods", []):
        m = _DURATION.search(w.get("duration", ""))
        if not (start and m):
            continue
        n, unit = int(m.group(1)), m.group(2).lower()
        end = end_date(start, months=n) if unit == "month" else end_date(start, days=n)
        w["startDate"], w["endDate"] = start.isoformat(), end.isoformat() if end else ""


def apply_user_details(base_facts: dict, details: dict) -> dict:
    """Returns a new facts dict. User-entered values win; fields they changed are listed in "userProvided"."""
    facts = copy.deepcopy(base_facts)
    provided: list[str] = []

    start = parse_date(details.get("startDate"))
    if start:
        facts["startDate"] = start.isoformat()
        _recompute_waiting_periods(facts, facts["startDate"])
        facts["flags"] = [f for f in facts.get("flags", []) if f.get("code") != "missing_start_date"]
        provided.append("startDate")

    if details.get("sumInsured"):
        facts["sumInsured"] = float(details["sumInsured"])
        provided.append("sumInsured")

    if details.get("members"):
        facts["members"] = [{"name": m["name"], "relation": m["relation"], "age": m.get("age")} for m in details["members"]]
        provided.append("members")

    if details.get("roomRentPerDay"):
        amount = float(details["roomRentPerDay"])
        room = facts.setdefault("roomRent", {"label": ""})
        room["amount"], room["unit"] = amount, "per day"
        if not room.get("citation"):
            room["label"] = f"Up to {format_inr(amount)} per day (from your policy schedule, entered by you)"
        provided.append("roomRentPerDay")

    if details.get("policyNumber"):
        facts["policyNumber"] = details["policyNumber"]
        provided.append("policyNumber")

    facts["userProvided"] = provided
    return facts
