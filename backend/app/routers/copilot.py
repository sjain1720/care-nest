from fastapi import APIRouter, HTTPException
from google.api_core.exceptions import GoogleAPIError
from google.genai import errors as genai_errors

from app.schemas import AskRequest, AskResponse
from app.services.copilot import answer

router = APIRouter(tags=["copilot"])

_GOOGLE_ERRORS = (GoogleAPIError, genai_errors.APIError)


@router.post("/copilot/ask", response_model=AskResponse)
def ask(body: AskRequest):
    """Claim Copilot: routes to the policy, bill/settlement or claim specialist; every quote is verified."""
    try:
        return answer(body.question.strip())
    except _GOOGLE_ERRORS as exc:
        raise HTTPException(502, f"A Google service failed while answering: {exc.__class__.__name__}") from exc


@router.post("/copilot/agent")
async def ask_agent(body: AskRequest):
    """Experimental: the same question answered by the Google ADK agent team (free text, not verified like /ask)."""
    from app.adk_copilot import run_copilot_agent  # imported lazily so the API starts even if ADK has a problem

    try:
        return await run_copilot_agent(body.question.strip())
    except _GOOGLE_ERRORS as exc:
        raise HTTPException(502, f"A Google service failed in the agent: {exc.__class__.__name__}") from exc
