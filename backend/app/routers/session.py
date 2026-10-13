from fastapi import APIRouter, Response

from app.services import case_store, policy_store

router = APIRouter(tags=["session"])


@router.delete("/session", status_code=204)
def delete_my_data():
    """Deletes this guest's claim, uploaded claim files, active policy choice and typed-in policy details."""
    case_store.delete_case()
    policy_store.delete_session_state()
    return Response(status_code=204)
