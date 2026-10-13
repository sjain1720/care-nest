"""Delete a guest's entire private data graph; shared synthetic templates survive."""
from google.cloud.firestore_v1.base_query import FieldFilter

from app.core.gcp import bucket, db
from app.core.session import reset_session, set_session
from app.services import case_store, policy_store
from app.services.session_registry import revoke_session


def delete_guest(sid: str) -> None:
    # Revoke before deletion so failed cleanup cannot restore API access.
    revoke_session(sid)
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
        policy_store.delete_session_state()
        db().collection("guestSessions").document(sid).delete()
    finally:
        reset_session(token)
