"""Claim diary: what the family sent, what the insurer replied, and the claim stage that follows. Pure Python."""
import secrets
from datetime import date

from app.services.policy_details import format_inr

USER_EVENT_KINDS = ("claim_sent", "letter_sent", "query_answered", "complaint_filed", "closed")
REPLY_OUTCOMES = ("paid_more", "explained", "no_change", "asks_for_papers", "rejected", "unclear")
# Usual waits; the UI tells users to check the latest rule before acting on them.
REPLY_DAYS = 14
DECISION_DAYS = 30

REPLY_STAGE = {
    "paid_more": "The insurer agreed to pay more",
    "explained": "The insurer explained the cuts",
    "no_change": "The insurer kept its decision – you can complain",
    "asks_for_papers": "The insurer asked for more papers",
    "rejected": "The insurer still refuses – you can complain",
    "unclear": "The insurer replied – read what it says",
}


def new_event_id() -> str:
    return "ev-" + secrets.token_hex(4)


def sorted_timeline(events: list[dict] | None) -> list[dict]:
    """Oldest first. Events on the same day keep the order they were added in."""
    return sorted(events or [], key=lambda e: e.get("date") or "")


def days_since(iso_date: str, today: date) -> int:
    try:
        return max(0, (today - date.fromisoformat(iso_date)).days)
    except ValueError:
        return 0


def _short(iso_date: str) -> str:
    try:
        return date.fromisoformat(iso_date).strftime("%d %b").lstrip("0")
    except ValueError:
        return iso_date


def stage_from_timeline(events: list[dict], has_decision: bool, today: date) -> str | None:
    """Claim stage from the latest diary entry, or None when the uploaded letters say more."""
    if has_decision:
        # A query answered during the hospital stay says nothing once the insurer has decided.
        events = [e for e in events if e.get("kind") != "query_answered"]
    if not events:
        return None
    latest = events[-1]
    kind, when = latest.get("kind"), latest.get("date") or ""
    if kind == "closed":
        return "Closed – you marked this claim as sorted"
    if kind == "reply":
        stage = REPLY_STAGE.get(latest.get("outcome"), REPLY_STAGE["unclear"])
        if latest.get("outcome") == "paid_more" and latest.get("newApprovedAmount"):
            stage += f" (now {format_inr(latest['newApprovedAmount'])})"
        return stage
    n = days_since(when, today)
    if kind == "claim_sent":
        if has_decision:
            return None
        if n > DECISION_DAYS:
            return f"Claim sent {n} days ago – no decision yet, ask the insurer"
        return f"Claim sent on {_short(when)} – waiting for the insurer's decision"
    if kind == "query_answered":
        return f"You answered the insurer's question on {_short(when)} – waiting for approval"
    if kind == "complaint_filed" and (latest.get("level") or 1) >= 2:
        who = "Bima Bharosa" if latest.get("level") == 2 else "the Insurance Ombudsman"
        return f"Complaint filed with {who} on {_short(when)} – waiting for their reply"
    if kind in ("letter_sent", "complaint_filed"):
        if n > REPLY_DAYS:
            return f"No reply after {n} days – you can complain to the next level"
        return f"Waiting for the insurer's reply (sent {_short(when)}, {n} day{'' if n == 1 else 's'} ago)"
    return None
