"""All of a guest's claims: the one being worked on, earlier ones kept in CareNest, and past claims typed in by hand."""
import re

from fastapi import APIRouter, HTTPException

from app.schemas import PastClaimIn
from app.services import case_store, policy_store
from app.services.claim_history import has_content, manual_claim, new_claim_id, newest_first, summarize_case
from app.services.privacy import mask_all

router = APIRouter(tags=["claims"])

_CLAIM_ID = re.compile(r"^cl-[0-9a-f]{8}$")


def _all_claims() -> list[dict]:
    current = case_store.get_case()
    head = [{**summarize_case(current, "current"), "current": True}] if has_content(current) else []
    return head + [{**c, "current": False} for c in newest_first(case_store.list_past_claims())]


def _find(claim_id: str) -> dict:
    if not _CLAIM_ID.match(claim_id):
        raise HTTPException(400, "Invalid claim.")
    past = case_store.get_past_claim(claim_id)
    if past is None:
        raise HTTPException(404, "Claim not found.")
    return past


@router.get("/claims")
def list_claims():
    return _all_claims()


@router.post("/claims/new")
def start_new_claim():
    case_store.start_new_claim()
    return _all_claims()


@router.post("/claims/past")
def add_past_claim(body: PastClaimIn):
    active = policy_store.get_active_policy_id()
    if not active:
        raise HTTPException(409, "Select a policy before adding a past claim.")
    entry = {**body.model_dump(exclude_none=True), "policyId": active}
    case_store.add_past_claim(manual_claim(mask_all(entry), new_claim_id()))
    return _all_claims()


@router.post("/claims/{claim_id}/open")
def open_claim(claim_id: str):
    past = _find(claim_id)
    if "case" not in past:
        raise HTTPException(400, "A claim you typed in has no files to open.")
    case_store.open_past_claim(claim_id, past["case"])
    return _all_claims()


@router.delete("/claims/{claim_id}")
def delete_claim(claim_id: str):
    case_store.delete_past_claim(claim_id, _find(claim_id))
    return _all_claims()
