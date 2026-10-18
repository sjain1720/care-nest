import hashlib
import json
import re
import asyncio
import contextvars
import queue
import threading

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from google.api_core.exceptions import GoogleAPIError, NotFound
from google.genai import errors as genai_errors

from app.schemas import ClaimDocuments, DocumentTaskUpdate, AskRequest, BillReviewIn, ChecklistUpdate, DisputePreparation, DisputeReview, QueryHelpRequest, ReplyRequest, TimelineEventIn
from app.services.sse import sse_event
from app.services import case_store, policy_store
from app.services.case_builder import build_case
from app.services.bill_policy import analyse_bill_policy, fingerprint
from app.services.case_ingest import apply_bill_review
from app.services.claim_tracker import new_event_id
from app.services.letter_writer import draft_letter
from app.services.letters import LETTER_KINDS
from app.services.privacy import mask_all
from app.services.query_help import explain_query
from app.services.reply_reader import read_reply_text
from app.services.dispute_inputs import current_dispute_inputs

router = APIRouter(tags=["case"])

_ITEM_ID = re.compile(r"^[a-z0-9-]{1,40}$")
_EVENT_ID = re.compile(r"^ev-[0-9a-f]{8}$")
_GOOGLE_ERRORS = (GoogleAPIError, genai_errors.APIError)


@router.get("/case")
def get_case():
    return build_case(case_store.get_case())


@router.get('/case/dispute/inputs', response_model=DisputePreparation)
def get_dispute_inputs():
    """Guest-owned source readiness and arithmetic for the upcoming ADK review."""
    return current_dispute_inputs()


@router.post('/case/dispute/review', response_model=DisputeReview)
async def review_dispute(body: AskRequest):
    from app.services.dispute_review import run_review
    return await run_review(body.question.strip())


@router.post('/case/dispute/review/stream')
def stream_dispute_review(body: AskRequest):
    from app.services.dispute_review import run_review
    events = queue.Queue()

    def work():
        try:
            result = asyncio.run(run_review(body.question.strip(),
                on_step=lambda step: events.put({'type': 'step', 'step': step.model_dump()})))
            events.put({'type': 'review', 'review': result.model_dump()})
        except Exception:
            events.put({'type': 'error', 'message': 'The decision review could not complete. Please retry.'})
        finally:
            events.put(None)

    threading.Thread(target=contextvars.copy_context().run, args=(work,), daemon=True).start()

    def stream():
        while (event := events.get()) is not None:
            yield sse_event(event)

    return StreamingResponse(stream(), media_type='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@router.get("/case/bill")
def get_bill():
    bill = case_store.get_case().get("bill")
    if not bill:
        raise HTTPException(404, "No hospital bill has been uploaded yet.")
    analysis = bill.get('policyAnalysis')
    if analysis:
        active = policy_store.get_active_policy()
        if not active or analysis.get('fingerprint') != fingerprint(active[0], active[1]['facts'], bill):
            bill = {**bill, 'policyAnalysis': None}
    return bill


@router.put("/case/bill")
def review_bill(body: BillReviewIn):
    """The family confirmed or corrected what was read from the bill; every check is re-run on their values."""
    try:
        return apply_bill_review(body.model_dump(exclude_none=True))
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/case/settlement")
def get_settlement():
    from app.services.claim_financials import settlement_view
    settlement = settlement_view(case_store.get_case())
    if not settlement:
        raise HTTPException(404, "No settlement letter has been uploaded yet.")
    return settlement


@router.get("/case/document/{doc_id}")
def get_case_document(doc_id: str):
    try:
        data, mime = case_store.load_file(doc_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except NotFound as exc:
        raise HTTPException(404, "Document not found.") from exc
    return Response(data, media_type=mime,
                    headers={"Content-Disposition": "inline", "Cache-Control": "private, max-age=300"})


@router.patch("/case/checklist/{item_id}")
def update_checklist_item(item_id: str, body: ChecklistUpdate):
    if not _ITEM_ID.match(item_id):
        raise HTTPException(400, "Invalid checklist item.")
    statuses = {**(case_store.get_case().get("checklistStatus") or {}), item_id: body.status}
    case_store.update_case({"checklistStatus": statuses})
    return build_case(case_store.get_case())


@router.post("/case/timeline")
def add_timeline_event(body: TimelineEventIn):
    if body.kind == 'payment_recorded' and body.paymentAmount is None:
        raise HTTPException(422, 'Enter the total amount actually received so far.')
    if body.kind == "outcome_recorded" and not (body.note or "").strip():
        raise HTTPException(422, "Write an outcome update before saving it.")
    if body.letterKind == 'document_response':
        from app.services.claim_flow import response_draft, FlowConflict
        try:
            current = response_draft()
            if any(getattr(body, key) != current[key] for key in ('claimKey', 'replyId', 'inputFingerprint')):
                raise FlowConflict('The reply or documents changed. Review a fresh response before marking it sent.')
        except FlowConflict as exc:
            raise HTTPException(409, str(exc)) from exc
        from app.services.claim_flow import response_fingerprint
        active = policy_store.get_active_policy()
        facts = active[1]['facts'] if active else {}
        def record(case):
            if case.get('flowId') != body.claimKey or response_fingerprint(case, facts) != body.inputFingerprint:
                raise FlowConflict('The reply or documents changed. Review the response again.')
            return {'timeline': case.get('timeline', []) + [mask_all({'id':new_event_id(), **body.model_dump(exclude_none=True)})]}
        try:
            case_store.mutate_case(record)
        except FlowConflict as exc:
            raise HTTPException(409, str(exc)) from exc
        return build_case(case_store.get_case())
    case_store.add_timeline_event(mask_all({"id": new_event_id(), **body.model_dump(exclude_none=True)}))
    return build_case(case_store.get_case())


@router.delete("/case/timeline/{event_id}")
def remove_timeline_event(event_id: str):
    if not _EVENT_ID.match(event_id):
        raise HTTPException(400, "Invalid diary entry.")
    if not case_store.remove_timeline_event(event_id):
        raise HTTPException(404, "Diary entry not found.")
    return build_case(case_store.get_case())


@router.post("/case/reply")
def add_reply(body: ReplyRequest):
    try:
        read_reply_text(body.text.strip())
    except _GOOGLE_ERRORS as exc:
        raise HTTPException(502, f"A Google service failed while reading the reply: {exc.__class__.__name__}") from exc
    return build_case(case_store.get_case())


@router.get("/case/letter")
def get_letter(kind: str = Query("clarification")):
    if kind not in LETTER_KINDS:
        raise HTTPException(400, f"kind must be one of {', '.join(LETTER_KINDS)}")
    try:
        if kind == "document_response":
            from app.services.claim_flow import response_draft, FlowConflict
            try:
                return response_draft()
            except FlowConflict as exc:
                raise HTTPException(409, str(exc)) from exc
        from app.services.claim_flow import ensure_context
        claim_key = ensure_context()
        case_before = case_store.get_case()
        relevant = {k:case_before.get(k) for k in ('flowId','bill','billHeader','settlement','rejection','documents','timeline','policyId')}
        active = policy_store.get_active_policy()
        fingerprint = hashlib.sha256(json.dumps([relevant,active],sort_keys=True,default=str).encode()).hexdigest()
        draft = draft_letter(kind)
        now = case_store.get_case()
        active_now = policy_store.get_active_policy()
        current_relevant = {k:now.get(k) for k in relevant}
        current_fingerprint = hashlib.sha256(json.dumps([current_relevant,active_now],sort_keys=True,default=str).encode()).hexdigest()
        if current_fingerprint != fingerprint:
            raise HTTPException(409, 'The selected claim or policy changed while preparing the letter. Open it again.')
        return {**draft,'claimKey':claim_key,'inputFingerprint':fingerprint}
    except _GOOGLE_ERRORS as exc:
        raise HTTPException(502, f"A Google service failed while drafting: {exc.__class__.__name__}") from exc


@router.post("/case/query-help")
def query_help(body: QueryHelpRequest):
    try:
        return explain_query(body.queryText.strip())
    except _GOOGLE_ERRORS as exc:
        raise HTTPException(502, f"A Google service failed while reading the query: {exc.__class__.__name__}") from exc


@router.post('/case/bill/evidence')
def get_bill_policy_evidence():
    try:
        return analyse_bill_policy()
    except LookupError as exc:
        raise HTTPException(409, str(exc)) from exc
    except _GOOGLE_ERRORS as exc:
        raise HTTPException(502, 'Policy comparison service failed. Please retry.') from exc


@router.get('/case/document-tasks',response_model=ClaimDocuments)
def get_document_tasks():
    from app.services.claim_flow import current_tasks
    return current_tasks()


@router.put('/case/document-tasks/{task_id}',response_model=ClaimDocuments)
def put_document_task(task_id: str, body: DocumentTaskUpdate):
    from app.services.claim_flow import update_task, FlowConflict
    try:
        return update_task(task_id, body)
    except FlowConflict as exc:
        raise HTTPException(409, str(exc)) from exc
