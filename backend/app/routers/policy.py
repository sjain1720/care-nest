import logging
import hashlib

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
from app.services.claim_flow import FlowConflict
from app.services.policy_ingest import UnsupportedFileError, process_upload

router = APIRouter(tags=["policy"])

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
_GOOGLE_ERRORS = (GoogleAPIError, genai_errors.APIError)
log = logging.getLogger(__name__)


@router.post("/documents", response_model=UploadResult)
def upload_document(file: UploadFile = File(...), docType: str = Form("auto"),
                    claimKey: str | None = Form(None), taskId: str | None = Form(None),
                    replaceExisting: bool = Form(False)):
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
        if claimKey:
            from app.services import case_store
            from app.services.claim_flow import task_list, link_uploaded
            case = case_store.get_case()
            if case.get('flowId') != claimKey:
                raise HTTPException(409, 'The selected claim changed. Return to documents before uploading.')
            if taskId and taskId not in {t['id'] for t in task_list(case)}:
                raise HTTPException(409, 'This requested item changed. Refresh the documents page.')
            if docType == 'auto':
                from app.services.policy_ingest import classify
                from app.services.ocr import ocr_first_page
                docType = classify([{'page':1,'text':ocr_first_page(data,mime)}])
            if taskId and docType == 'Policy document':
                raise HTTPException(400, 'Upload a supporting file for this item; change the selected policy separately.')
            document_id = ('img-' if is_image(mime) else 'doc-') + hashlib.sha256(data).hexdigest()[:16]
            existing_type = {'Hospital bill': 'bill', 'Settlement letter': 'settlement', 'Rejection letter': 'rejection'}.get(docType)
            known = any(d['id'] == document_id for d in case.get('documents', []))
            if existing_type and case.get(existing_type) and not known and not replaceExisting:
                raise HTTPException(409, 'This claim already has this document. Choose Replace current document or start a new claim first.')
            with case_store.guard_flow(claimKey):
                result = process_upload(data, file.filename or 'document', docType, mime)
                if result.detectedType != 'Policy document':
                    result.documentId = document_id
                    if taskId:
                        link_uploaded(taskId, claimKey, document_id)
                return result
        return process_upload(data, file.filename or "document", docType, mime)
    except FlowConflict as exc:
        raise HTTPException(409, str(exc)) from exc
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
        if getattr(exc, 'page_start', None):
            if code == 429:
                raise HTTPException(502,
                    f'OCR request quota is busy while reading PDF pages {exc.page_start}–{exc.page_end}. '
                    'Wait about a minute, then retry the same file; successfully saved pages will be reused.') from exc
            raise HTTPException(502,
                f'Google could not read PDF pages {exc.page_start}–{exc.page_end}'
                + (f' (code {code})' if code else '')
                + '. Automatic recovery did not finish. Retry the same file; successfully saved page groups will be reused.') from exc
        raise HTTPException(502, detail + f'. {recovery} Any successfully saved policy pages and indexing batches will be reused.') from exc


def _active_policy() -> tuple[str, dict]:
    active = store.get_active_policy()
    if not active:
        if store.has_legacy_sample_policy():
            raise HTTPException(404, {'code': 'sample_policy_requires_upload',
                                     'message': 'The saved policy is an earlier sample, not your uploaded policy. Upload your own policy PDF.'})
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
    return PolicyFacts.model_validate(store.get_active_policy()[1]["facts"])


@router.get("/policy/document")
def get_policy_document(policyId: str | None = None):
    policy_id, _ = _active_policy()
    if policyId is not None and policyId != policy_id:
        raise HTTPException(409, 'This source belongs to a previous policy. Ask again using the current policy.')
    return Response(store.load_original(policy_id), media_type="application/pdf",
                    headers={"Content-Disposition": 'inline; filename="policy.pdf"', "Cache-Control": "private, max-age=300"})
