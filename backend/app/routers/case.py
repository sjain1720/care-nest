import re

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from google.api_core.exceptions import GoogleAPIError, NotFound
from google.genai import errors as genai_errors

from app.schemas import ChecklistUpdate, QueryHelpRequest
from app.services import case_store
from app.services.case_builder import build_case
from app.services.letter_writer import draft_letter
from app.services.letters import LETTER_KINDS
from app.services.query_help import explain_query

router = APIRouter(tags=["case"])

_ITEM_ID = re.compile(r"^[a-z0-9-]{1,40}$")
_GOOGLE_ERRORS = (GoogleAPIError, genai_errors.APIError)


@router.get("/case")
def get_case():
    return build_case(case_store.get_case())


@router.get("/case/bill")
def get_bill():
    bill = case_store.get_case().get("bill")
    if not bill:
        raise HTTPException(404, "No hospital bill has been uploaded yet.")
    return bill


@router.get("/case/settlement")
def get_settlement():
    settlement = case_store.get_case().get("settlement")
    if not settlement:
        raise HTTPException(404, "No settlement letter has been uploaded yet.")
    return settlement


@router.get("/case/document/{doc_id}")
def get_case_document(doc_id: str):
    try:
        pdf = case_store.load_pdf(doc_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except NotFound as exc:
        raise HTTPException(404, "Document not found.") from exc
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": "inline", "Cache-Control": "private, max-age=300"})


@router.patch("/case/checklist/{item_id}")
def update_checklist_item(item_id: str, body: ChecklistUpdate):
    if not _ITEM_ID.match(item_id):
        raise HTTPException(400, "Invalid checklist item.")
    statuses = {**(case_store.get_case().get("checklistStatus") or {}), item_id: body.status}
    case_store.update_case({"checklistStatus": statuses})
    return build_case(case_store.get_case())


@router.get("/case/letter")
def get_letter(kind: str = Query("clarification")):
    if kind not in LETTER_KINDS:
        raise HTTPException(400, f"kind must be one of {', '.join(LETTER_KINDS)}")
    try:
        return draft_letter(kind)
    except _GOOGLE_ERRORS as exc:
        raise HTTPException(502, f"A Google service failed while drafting: {exc.__class__.__name__}") from exc


@router.post("/case/query-help")
def query_help(body: QueryHelpRequest):
    try:
        return explain_query(body.queryText.strip())
    except _GOOGLE_ERRORS as exc:
        raise HTTPException(502, f"A Google service failed while reading the query: {exc.__class__.__name__}") from exc
