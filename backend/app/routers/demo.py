from fastapi import APIRouter, HTTPException
from google.api_core.exceptions import GoogleAPIError
from google.genai import errors as genai_errors

from app.services.demo_loader import load_demo_case
from app.services.example_workspace import ensure_example_workspace, ExampleNotPrepared

router = APIRouter(tags=["demo"])

_GOOGLE_ERRORS = (GoogleAPIError, genai_errors.APIError)


@router.post('/demo/ensure')
def ensure_example():
    try:
        return ensure_example_workspace()
    except ExampleNotPrepared as exc:
        raise HTTPException(503, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/demo/load")
def load_demo():
    """Runs the synthetic demo policy, bill and settlement letter through the real pipeline (about 1-2 minutes the first time)."""
    try:
        return {"loaded": load_demo_case()}
    except FileNotFoundError as exc:
        raise HTTPException(500, str(exc)) from exc
    except _GOOGLE_ERRORS as exc:
        raise HTTPException(502, f"A Google service failed while loading the demo: {exc.__class__.__name__}") from exc
