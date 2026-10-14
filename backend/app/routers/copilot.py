import asyncio
import contextvars
import logging
import queue
import threading

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from google.api_core.exceptions import GoogleAPIError
from google.genai import errors as genai_errors

from app.schemas import AskRequest, AskResponse
from app.services.copilot import answer
from app.services.conversation import prepare, remember, clear_threads
from app.services.sse import sse_event

router = APIRouter(tags=["copilot"])
log = logging.getLogger(__name__)

_GOOGLE_ERRORS = (GoogleAPIError, genai_errors.APIError)


@router.post("/copilot/ask", response_model=AskResponse)
def ask(body: AskRequest):
    """Claim Copilot: routes to the policy, bill/settlement or claim specialist; every quote is verified."""
    try:
        question, context = prepare(body.question.strip(), body.conversationId)
        result = answer(question, language=body.language, original_question=body.question)
        remember(context, result.answer)
        return result
    except _GOOGLE_ERRORS as exc:
        raise HTTPException(502, f"A Google service failed while answering: {exc.__class__.__name__}") from exc


@router.post("/copilot/ask/stream")
def ask_stream(body: AskRequest):
    """Same as /ask, but streams each agent step as it happens (Server-Sent Events), then the answer."""
    events: queue.Queue = queue.Queue()

    def work() -> None:
        try:
            question, context = prepare(body.question.strip(), body.conversationId)
            result = answer(question, on_step=lambda s: events.put({"type": "step", "step": s.model_dump()}), language=body.language, original_question=body.question)
            remember(context, result.answer)
            events.put({"type": "answer", "answer": result.answer.model_dump()})
        except Exception as exc:  # report any failure to the browser instead of leaving the stream hanging
            log.exception("Streaming answer failed")
            friendly = "A Google service failed while answering." if isinstance(exc, _GOOGLE_ERRORS) else "Something went wrong while answering."
            events.put({"type": "error", "message": friendly})
        finally:
            events.put(None)

    # copy_context: the worker thread keeps this request's guest session.
    threading.Thread(target=contextvars.copy_context().run, args=(work,), daemon=True).start()

    def stream():
        while (item := events.get()) is not None:
            yield sse_event(item)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/copilot/agent")
async def ask_agent(body: AskRequest):
    """Legacy URL normalized through the same verified hybrid chat boundary."""
    def work():
        question, context = prepare(body.question.strip(), body.conversationId)
        result = answer(question, language=body.language, original_question=body.question)
        remember(context, result.answer)
        return {'steps': [step.model_dump() for step in result.steps],
                'text': result.answer.summary, 'answer': result.answer.model_dump()}
    try:
        return await asyncio.to_thread(work)
    except _GOOGLE_ERRORS as exc:
        raise HTTPException(502, f"A Google service failed while answering: {exc.__class__.__name__}") from exc



@router.delete('/copilot/conversation', status_code=204)
def reset_conversation():
    clear_threads()
