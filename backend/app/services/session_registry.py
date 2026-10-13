"""Server-issued bearer identities with a fixed expiry, shared across instances."""
from datetime import datetime, timezone

from app.core.gcp import db
from app.core.session import TTL, is_valid, new_session_id


def resolve_session(candidate: str | None) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    registry = db().collection("guestSessions")
    if is_valid(candidate):
        snap = registry.document(candidate).get()
        data = snap.to_dict() or {} if snap.exists else {}
        deadline = data.get("expiresAt")
        if isinstance(deadline, datetime) and deadline > now and not data.get("revoked"):
            return candidate, deadline
    sid = new_session_id()
    deadline = now + TTL
    # expiresAt intentionally is not a Firestore TTL field: the cleanup worker
    # must remove nested data and blobs before removing this identity.
    registry.document(sid).create({"createdAt": now, "expiresAt": deadline})
    return sid, deadline


def revoke_session(sid: str) -> None:
    db().collection("guestSessions").document(sid).set({"revoked": True}, merge=True)
