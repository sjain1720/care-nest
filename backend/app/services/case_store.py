"""Firestore + Storage for the single demo case.

cases/current     documents[], billHeader{}, bill{}, settlement{}   (structured data only – raw bill text is never stored)
Storage           cases/current/{docId}.pdf
"""
import re

from google.cloud import firestore

from app.core.gcp import bucket, db

CASE_ID = "current"
DOC_ID = re.compile(r"^doc-[0-9a-f]{16}$")


def _case():
    return db().collection("cases").document(CASE_ID)


def get_case() -> dict:
    snap = _case().get()
    return {"id": CASE_ID, **(snap.to_dict() or {})} if snap.exists else {"id": CASE_ID}


def update_case(data: dict) -> None:
    _case().set({**data, "updatedAt": firestore.SERVER_TIMESTAMP}, merge=True)


def add_document(doc: dict) -> None:
    current = [d for d in get_case().get("documents", []) if d["id"] != doc["id"]]
    update_case({"documents": current + [doc]})


def save_pdf(doc_id: str, pdf_bytes: bytes) -> None:
    bucket().blob(f"cases/{CASE_ID}/{doc_id}.pdf").upload_from_string(pdf_bytes, content_type="application/pdf")


def load_pdf(doc_id: str) -> bytes:
    if not DOC_ID.match(doc_id):
        raise ValueError("Invalid document id")
    return bucket().blob(f"cases/{CASE_ID}/{doc_id}.pdf").download_as_bytes()
