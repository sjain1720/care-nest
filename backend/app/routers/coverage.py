from fastapi import APIRouter

from app.schemas import CoverageEstimate, CoveragePreviewInput
from app.services.coverage import estimate_coverage, get_guest_coverage

router = APIRouter(tags=['coverage'])


@router.get('/coverage', response_model=CoverageEstimate)
def get_coverage():
    """Inputs come only from this guest's selected policy and stored ledger."""
    return get_guest_coverage()


@router.post('/coverage/preview', response_model=CoverageEstimate)
def preview_coverage(body: CoveragePreviewInput):
    """Mock UI calculator only. Does not persist or establish the guest's balance."""
    return estimate_coverage(body.policy.model_dump(), [c.model_dump() for c in body.claims], demo=True)
