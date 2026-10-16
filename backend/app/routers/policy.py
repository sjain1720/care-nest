import logging

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from google.api_core.exceptions import GoogleAPIError
from google.genai import errors as genai_errors
from pypdf.errors import PdfReadError

from app.schemas import PolicyDetailsInput, PolicyFacts, TreatmentPlanInput, TreatmentPlanPreparation, UploadResult
from app.services.treatment_planning import current_plan
from app.services import policy_store as store
from app.services.file_types import detect_mime, is_image, UnreadableDocumentError
from app.services.ocr import PdfTooLongError
from app.services.policy_details import apply_user_details
from app.services.policy_ingest import UnsupportedFileError, process_upload

router = APIRouter(tags=["policy"])

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
_GOOGLE_ERRORS = (GoogleAPIError, genai_errors.APIError)
log = logging.getLogger(__name__)


@router.post("/documents", response_model=UploadResult)
def upload_document(file: UploadFile = File(...), docType: str = Form("auto")):
    """A PDF, or a photo (JPEG, PNG, WebP) of a bill or letter. docType: "auto" (detect from page 1) or one of policy_ingest.DOC_TYPES."""
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "This file is larger than 20 MB.")
    mime = detect_mime(data)
    if mime is None:
        raise HTTPException(415, "Upload a PDF, or a photo (JPG, PNG or WebP).")
    if is_image(mime) and docType == "Policy document":
        raise HTTPException(415, "Upload the policy as a PDF. Photos work for bills and letters.")
    try:
        return process_upload(data, file.filename or "document", docType, mime)
    except (PdfTooLongError, UnsupportedFileError, UnreadableDocumentError) as exc:
        raise HTTPException(422, str(exc)) from exc
    except (PdfReadError, IndexError) as exc:
        raise HTTPException(422, "This PDF is empty, encrypted or unreadable. Upload an unlocked, readable PDF.") from exc
    except _GOOGLE_ERRORS as exc:
        code = getattr(exc, 'code', None)
        code = code if isinstance(code, int) else None
        log.warning('Document service failed error=%s code=%s', type(exc).__name__, code)
        reason = ('Google AI is busy right now' if code == 429 else
                  'Google refused access to document processing' if code in (401, 403) else
                  'Google could not complete document processing')
        detail = f'{reason}' + (f' (code {code})' if code else '')
        recovery = ('Wait about a minute, then retry the same file.' if code == 429 else 'Retry the same file.')
        raise HTTPException(502, detail + f'. {recovery} Saved policy pages and indexing batches will be reused.') from exc


def _active_policy() -> tuple[str, dict]:
    active = store.get_active_policy()
    if not active:
        raise HTTPException(404, "No policy has been uploaded yet.")
    return active


@router.get("/policy", response_model=PolicyFacts)
def get_policy():
    return _active_policy()[1]["facts"]


@router.post('/policy/treatment-plan/prepare', response_model=TreatmentPlanPreparation)
def prepare_treatment_plan(body: TreatmentPlanInput):
    return current_plan(body)


@router.put("/policy/details", response_model=PolicyFacts)
def update_policy_details(body: PolicyDetailsInput):
    """Saves schedule details this guest typed in (in their own session) and recomputes the facts from the document's facts."""
    _, doc = _active_policy()
    details = body.model_dump(exclude_none=True)
    facts = PolicyFacts.model_validate(apply_user_details(doc.get("baseFacts") or doc["facts"], details))
    store.save_session_details(details)
    return facts


@router.get("/policy/document")
def get_policy_document():
    policy_id, _ = _active_policy()
    return Response(store.load_original(policy_id), media_type="application/pdf",
                    headers={"Content-Disposition": 'inline; filename="policy.pdf"', "Cache-Control": "private, max-age=300"})
