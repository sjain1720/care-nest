from io import BytesIO

from fastapi import APIRouter
from pypdf import PdfWriter

from app.core.config import get_settings
from app.core.gcp import bucket, db, gemini
from app.services.ocr import ocr_pdf

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return {"status": "ok", "service": "carenest"}


def _check(fn):
    try:
        return {"ok": True, "detail": fn()}
    except Exception as exc:  # report every failure instead of stopping at the first one
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _blank_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


@router.get("/diag")
def diag():
    """Calls each Google service once to prove credentials and permissions work."""
    s = get_settings()
    checks = {
        "gemini": _check(
            lambda: gemini().models.generate_content(model=s.gemini_model, contents="Reply with the word OK.").text.strip()
        ),
        "embedding": _check(
            lambda: len(gemini().models.embed_content(model=s.embedding_model, contents="room rent limit").embeddings[0].values)
        ),
        "firestore": _check(
            lambda: (db().collection("healthcheck").document("ping").set({"ok": True}), "write ok")[1]
        ),
        "storage": _check(lambda: bucket().exists()),
        "document_ai": _check(lambda: f"{len(ocr_pdf(_blank_pdf()))} page(s) processed"),
    }
    return {"all_ok": all(c["ok"] for c in checks.values()), "checks": checks}
