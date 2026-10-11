from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from google.api_core.exceptions import NotFound

from app.services import case_store
from app.services.case_builder import build_case

router = APIRouter(tags=["case"])


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
