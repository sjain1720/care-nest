"""Delete a guest's entire private data graph; shared synthetic templates survive."""
from google.cloud.firestore_v1.base_query import FieldFilter

from app.core.gcp import bucket, db
from app.core.session import reset_session, set_session
from app.services import case_store, policy_store
from app.services.session_registry import revoke_session


def delete_guest(sid: str) -> None:
    # Revoke before deletion so failed cleanup cannot restore API access.
    revoke_session(sid)
    # An issued browser identity also owns its separate fictional workspace.
    record = db().collection('guestSessions').document(sid).get().to_dict() or {}
    child_id = record.get('exampleSessionId') if isinstance(record, dict) else None
    if isinstance(child_id, str) and child_id != sid:
        child = db().collection('guestSessions').document(child_id).get().to_dict() or {}
        if isinstance(child, dict) and child.get('parentSessionId') == sid:
            delete_guest(child_id)
    token = set_session(sid)
    try:
        case_store.delete_case()
        owned = db().collection("policies").where(filter=FieldFilter("ownerSessionId", "==", sid))
        for policy in owned.stream():
            if policy.to_dict().get("isDemoTemplate"):
                continue
            for blob in bucket().list_blobs(prefix=f"policies/{policy.id}/"):
                blob.delete()
            db().recursive_delete(policy.reference)
        db().recursive_delete(db().collection("conversations").document(sid))
        policy_store.delete_session_state()
        db().collection("guestSessions").document(sid).delete()
    finally:
        reset_session(token)
