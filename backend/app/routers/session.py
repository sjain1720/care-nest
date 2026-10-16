from fastapi import APIRouter, Response
from hashlib import sha256

from app.core.session import COOKIE, expiry, root_session_id, session_id
from app.services import policy_store
from app.services.data_lifecycle import delete_guest

router = APIRouter(tags=["session"])


@router.get("/session")
def get_session():
    state = policy_store.get_active_policy()
    return {"workspaceKey": sha256(session_id().encode()).hexdigest()[:16], "expiresAt": expiry().isoformat(), "mode": "live_demo" if state and state[1].get("isDemoTemplate") else "guest"}


@router.delete("/session", status_code=204)
def delete_my_data():
    """Revokes the identity and deletes owned files, policy subcollections and claims."""
    delete_guest(root_session_id())
    response = Response(status_code=204)
    response.delete_cookie(COOKIE, path="/", httponly=True, samesite="lax")
    return response
