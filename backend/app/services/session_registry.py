"""Server-issued bearer identities with a fixed expiry, shared across instances."""
from datetime import datetime, timezone

from app.core.gcp import db
from google.cloud import firestore
from app.core.session import TTL, is_valid, new_session_id


def resolve_session(candidate: str | None) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    registry = db().collection("guestSessions")
    if is_valid(candidate):
        snap = registry.document(candidate).get()
        data = snap.to_dict() or {} if snap.exists else {}
        deadline = data.get("expiresAt")
        if isinstance(deadline, datetime) and deadline > now and not data.get("revoked") and not data.get('parentSessionId'):
            return candidate, deadline
    sid = new_session_id()
    deadline = now + TTL
    # expiresAt intentionally is not a Firestore TTL field: the cleanup worker
    # must remove nested data and blobs before removing this identity.
    registry.document(sid).create({"createdAt": now, "expiresAt": deadline})
    return sid, deadline


def revoke_session(sid: str) -> None:
    db().collection("guestSessions").document(sid).set({"revoked": True}, merge=True)


def resolve_example_session(parent_id: str, deadline: datetime) -> str:
    """Server-owned child identity; a workspace selector never supplies an owner ID."""
    client = db()
    registry = client.collection('guestSessions')
    parent = registry.document(parent_id)

    @firestore.transactional
    def resolve(transaction):
        parent_snap = parent.get(transaction=transaction)
        state = parent_snap.to_dict() or {}
        if not parent_snap.exists or state.get('revoked') or state.get('expiresAt') != deadline:
            raise ValueError('The browser identity is no longer active')
        child_id = state.get('exampleSessionId')
        if is_valid(child_id):
            snap = registry.document(child_id).get(transaction=transaction)
            child = snap.to_dict() or {} if snap.exists else {}
            if child.get('parentSessionId') == parent_id and not child.get('revoked') and child.get('expiresAt') == deadline:
                return child_id
        child_id = new_session_id()
        transaction.create(registry.document(child_id), {
            'createdAt': datetime.now(timezone.utc), 'expiresAt': deadline,
            'parentSessionId': parent_id, 'workspace': 'example',
        })
        transaction.set(parent, {'exampleSessionId': child_id}, merge=True)
        return child_id

    return resolve(client.transaction())
