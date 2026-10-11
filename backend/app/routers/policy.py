from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from google.api_core.exceptions import GoogleAPIError
from google.genai import errors as genai_errors

from app.schemas import PolicyDetailsInput, PolicyFacts, UploadResult
from app.services import policy_store as store
from app.services.ocr import PdfTooLongError
from app.services.policy_details import apply_user_details
from app.services.policy_ingest import process_upload

router = APIRouter(tags=["policy"])

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
_GOOGLE_ERRORS = (GoogleAPIError, genai_errors.APIError)


@router.post("/documents", response_model=UploadResult)
def upload_document(file: UploadFile = File(...), docType: str = Form("auto")):
    """docType: "auto" (detect from page 1) or one of policy_ingest.DOC_TYPES."""
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "This file is larger than 20 MB.")
    if not data.startswith(b"%PDF"):
        raise HTTPException(415, "Only PDF files are supported.")
    try:
        return process_upload(data, file.filename or "document.pdf", docType)
    except PdfTooLongError as exc:
        raise HTTPException(422, str(exc)) from exc
    except _GOOGLE_ERRORS as exc:
        raise HTTPException(502, f"A Google service failed while reading the file: {exc.__class__.__name__}") from exc


def _active_policy() -> tuple[str, dict]:
    policy_id = store.get_active_policy_id()
    doc = store.get_policy(policy_id) if policy_id else None
    if not doc or doc.get("status") != "ready":
        raise HTTPException(404, "No policy has been uploaded yet.")
    return policy_id, doc


@router.get("/policy", response_model=PolicyFacts)
def get_policy():
    return _active_policy()[1]["facts"]


@router.put("/policy/details", response_model=PolicyFacts)
def update_policy_details(body: PolicyDetailsInput):
    """Saves schedule details the user typed in and recomputes the facts from the document's own facts."""
    policy_id, doc = _active_policy()
    details = body.model_dump(exclude_none=True)
    facts = PolicyFacts.model_validate(apply_user_details(doc.get("baseFacts") or doc["facts"], details))
    store.save_policy(policy_id, {"userDetails": details, "facts": facts.model_dump()})
    return facts


@router.get("/policy/document")
def get_policy_document():
    policy_id, _ = _active_policy()
    return Response(store.load_original(policy_id), media_type="application/pdf",
                    headers={"Content-Disposition": 'inline; filename="policy.pdf"', "Cache-Control": "private, max-age=300"})
