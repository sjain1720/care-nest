"""Upload -> OCR -> pages -> clauses + embeddings -> verified facts -> active policy."""
import hashlib

from app.schemas import UploadResult
from app.services import policy_store as store
from app.services.clauses import split_into_clauses
from app.services.embeddings import embed_texts
from app.services.ocr import ocr_pdf
from app.services.policy_extract import build_policy_facts, extract_policy_facts

_POLICY_HINTS = ("sum insured", "waiting period", "policy wording", "exclusion", "policyholder", "insured person")
_OTHER_TYPES = (
    ("Settlement letter", ("settlement letter", "amount approved", "claim settled")),
    ("Rejection letter", ("repudiat", "claim is rejected", "claim has been rejected")),
    ("Discharge summary", ("discharge summary",)),
    ("Hospital bill", ("final bill", "itemised bill", "itemized bill", "invoice")),
)


def classify(pages: list[dict]) -> str:
    head = " ".join(p["text"] for p in pages[:3]).lower()
    if sum(hint in head for hint in _POLICY_HINTS) >= 2:
        return "Policy document"
    for name, hints in _OTHER_TYPES:
        if any(h in head for h in hints):
            return name
    return "Policy document"


def process_upload(pdf_bytes: bytes, filename: str) -> UploadResult:
    doc_id = "pol-" + hashlib.sha256(pdf_bytes).hexdigest()[:16]

    # Same file uploaded again: reuse the earlier result instead of paying for OCR and Gemini twice.
    existing = store.get_policy(doc_id)
    if existing and existing.get("status") == "ready":
        store.set_active_policy(doc_id)
        return UploadResult(detectedType="Policy document", pages=existing.get("pageCount", 0), policyId=doc_id, reused=True)

    pages = ocr_pdf(pdf_bytes)
    doc_type = classify(pages)
    if doc_type != "Policy document":
        return UploadResult(detectedType=doc_type, pages=len(pages),
                            message="Read successfully. Bills and letters are analysed in the next phase.")

    store.save_original(doc_id, pdf_bytes)
    store.save_policy(doc_id, {"status": "processing", "filename": filename, "pageCount": len(pages)})
    store.save_pages(doc_id, pages)

    clauses = split_into_clauses(pages)
    vectors = embed_texts([f"{c.label} {c.title}\n{c.text}" for c in clauses], "RETRIEVAL_DOCUMENT")
    store.save_clauses(doc_id, clauses, vectors)

    facts = build_policy_facts(doc_id, extract_policy_facts(pages), pages)
    # baseFacts = what the document says; facts = baseFacts + details the user types in later.
    store.save_policy(doc_id, {"status": "ready", "baseFacts": facts.model_dump(), "facts": facts.model_dump(),
                               "clauseCount": len(clauses)})
    store.set_active_policy(doc_id)
    return UploadResult(detectedType=doc_type, pages=len(pages), policyId=doc_id)
