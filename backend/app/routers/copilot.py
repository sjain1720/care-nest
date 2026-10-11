import logging
import queue
import threading

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from google.api_core.exceptions import GoogleAPIError
from google.genai import errors as genai_errors

from app.schemas import AskRequest, AskResponse
from app.services.copilot import answer
from app.services.sse import sse_event

router = APIRouter(tags=["copilot"])
log = logging.getLogger(__name__)

_GOOGLE_ERRORS = (GoogleAPIError, genai_errors.APIError)


@router.post("/copilot/ask", response_model=AskResponse)
def ask(body: AskRequest):
    """Claim Copilot: routes to the policy, bill/settlement or claim specialist; every quote is verified."""
    try:
        return answer(body.question.strip())
    except _GOOGLE_ERRORS as exc:
        raise HTTPException(502, f"A Google service failed while answering: {exc.__class__.__name__}") from exc


@router.post("/copilot/ask/stream")
def ask_stream(body: AskRequest):
    """Same as /ask, but streams each agent step as it happens (Server-Sent Events), then the answer."""
    events: queue.Queue = queue.Queue()

    def work() -> None:
        try:
            result = answer(body.question.strip(), on_step=lambda s: events.put({"type": "step", "step": s.model_dump()}))
            events.put({"type": "answer", "answer": result.answer.model_dump()})
        except Exception as exc:  # report any failure to the browser instead of leaving the stream hanging
            log.exception("Streaming answer failed")
            friendly = "A Google service failed while answering." if isinstance(exc, _GOOGLE_ERRORS) else "Something went wrong while answering."
            events.put({"type": "error", "message": friendly})
        finally:
            events.put(None)

    threading.Thread(target=work, daemon=True).start()

    def stream():
        while (item := events.get()) is not None:
            yield sse_event(item)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/copilot/agent")
async def ask_agent(body: AskRequest):
    """Experimental: the same question answered by the Google ADK agent team (free text, not verified like /ask)."""
    from app.adk_copilot import run_copilot_agent  # imported lazily so the API starts even if ADK has a problem

    try:
        return await run_copilot_agent(body.question.strip())
    except _GOOGLE_ERRORS as exc:
        raise HTTPException(502, f"A Google service failed in the agent: {exc.__class__.__name__}") from exc
