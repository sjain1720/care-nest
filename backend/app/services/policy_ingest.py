"""Upload -> (detect type) -> policy pipeline (OCR, clauses, embeddings, verified facts) or bill/letter pipeline."""
import hashlib

from app.schemas import UploadResult
from app.services import policy_store as store
from app.services.case_ingest import process_case_document
from app.services.clauses import split_into_clauses
from app.services.embeddings import embed_texts
from app.services.ocr import ocr_first_page, ocr_pdf
from app.services.policy_extract import build_policy_facts, extract_policy_facts

DOC_TYPES = ("Policy document", "Hospital bill", "Settlement letter", "Rejection letter", "Discharge summary", "Other")

_POLICY_HINTS = ("sum insured", "waiting period", "policy wording", "exclusion", "policyholder", "insured person")
_OTHER_TYPES = (
    ("Settlement letter", ("settlement letter", "amount approved", "claim settled", "approved amount", "amount settled")),
    ("Rejection letter", ("repudiat", "claim is rejected", "claim has been rejected", "denial of claim")),
    ("Discharge summary", ("discharge summary",)),
    ("Hospital bill", ("final bill", "itemised bill", "itemized bill", "invoice", "bill no", "ip bill", "bill of supply", "receipt")),
)


def classify(pages: list[dict]) -> str:
    head = " ".join(p["text"] for p in pages[:3]).lower()
    if sum(hint in head for hint in _POLICY_HINTS) >= 2:
        return "Policy document"
    for name, hints in _OTHER_TYPES:
        if any(h in head for h in hints):
            return name
    return "Other"


def process_upload(pdf_bytes: bytes, filename: str, doc_type: str = "auto") -> UploadResult:
    if doc_type not in DOC_TYPES:
        doc_type = classify([{"page": 1, "text": ocr_first_page(pdf_bytes)}])
    if doc_type != "Policy document":
        return process_case_document(pdf_bytes, filename, doc_type)
    return ingest_policy(pdf_bytes, filename)


def ingest_policy(pdf_bytes: bytes, filename: str) -> UploadResult:
    doc_id = "pol-" + hashlib.sha256(pdf_bytes).hexdigest()[:16]

    # Same file uploaded again: reuse the earlier result instead of paying for OCR and Gemini twice.
    existing = store.get_policy(doc_id)
    if existing and existing.get("status") == "ready":
        store.set_active_policy(doc_id)
        return UploadResult(detectedType="Policy document", pages=existing.get("pageCount", 0), policyId=doc_id, reused=True)

    pages = ocr_pdf(pdf_bytes)
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
    return UploadResult(detectedType="Policy document", pages=len(pages), policyId=doc_id)
