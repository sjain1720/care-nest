"""Upload -> (detect type) -> policy pipeline (OCR, clauses, embeddings, verified facts) or bill/letter pipeline."""
import hashlib
import logging
import time

from google.genai.errors import ClientError

from app.schemas import UploadResult
from app.core.session import session_id, expiry
from app.services import policy_store as store
from app.services.case_ingest import process_case_document
from app.services.clauses import split_into_clauses
from app.services.embeddings import embed_texts
from app.services.file_types import PDF, is_image
from app.services.ocr import ocr_first_page, ocr_pdf
from app.services.policy_extract import build_policy_facts, extract_policy_facts

log = logging.getLogger(__name__)

DOC_TYPES = ("Policy document", "Hospital bill", "Settlement letter", "Rejection letter", "Insurer reply", "Discharge summary", "Other")


class UnsupportedFileError(ValueError):
    pass

_POLICY_HINTS = ("sum insured", "waiting period", "policy wording", "exclusion", "policyholder", "insured person")
_OTHER_TYPES = (
    ("Insurer reply", ("your letter dated", "your email dated", "your mail dated", "with reference to your", "your grievance", "your complaint")),
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


def process_upload(data: bytes, filename: str, doc_type: str = "auto", mime: str = PDF) -> UploadResult:
    source_text = None
    if doc_type not in DOC_TYPES:
        source_text = ocr_first_page(data, mime)
        doc_type = classify([{"page": 1, "text": source_text}])
    if doc_type != "Policy document":
        return process_case_document(data, filename, doc_type, mime, source_text=source_text)
    if is_image(mime):
        raise UnsupportedFileError("This looks like a policy document. Upload the policy as a PDF – photos work for bills and letters.")
    return ingest_policy(data, filename)


def ingest_policy(pdf_bytes: bytes, filename: str, shared_demo: bool = False) -> UploadResult:
    started_at = time.monotonic()
    digest = hashlib.sha256(pdf_bytes).hexdigest()[:16]
    doc_id = "demo-" + digest if shared_demo else f"pol-{session_id()}-{digest}"

    # Same file uploaded again: reuse the earlier result instead of paying for OCR and Gemini twice.
    existing = store.get_policy(doc_id)
    if existing and existing.get("status") == "ready":
        store.set_active_policy(doc_id)
        return UploadResult(detectedType="Policy document", pages=existing.get("pageCount", 0), policyId=doc_id, reused=True)

    store.save_policy(doc_id, {"status": "processing", "ownerSessionId": None if shared_demo else session_id(),
                               "isDemoTemplate": shared_demo, "expireAt": None if shared_demo else expiry()})
    stage = "reading_pages"
    try:
        # Only this guest's content-hash policy (or the exact shared demo) can be resumed.
        # A partial page write is never treated as a complete reading.
        saved = store.load_pages(doc_id) if existing and existing.get("pageCount") else {}
        expected = (existing or {}).get("pageCount", 0)
        complete = expected > 0 and set(saved) == set(range(1, expected + 1))
        if complete:
            pages = [{"page": n, "text": saved[n]} for n in sorted(saved)]
        else:
            store.save_policy(doc_id, {"processingStage": stage})
            pages = ocr_pdf(pdf_bytes)
            store.save_original(doc_id, pdf_bytes)
            store.save_policy(doc_id, {"filename": filename, "pageCount": len(pages)})
            store.save_pages(doc_id, pages)

        stage = "embedding_clauses"
        store.save_policy(doc_id, {"processingStage": stage})
        clauses = split_into_clauses(pages)
        indexed = store.load_clause_index(doc_id) if complete else {}
        pending = [c for c in clauses if indexed.get(c.clause_id) != store.clause_index_stamp(c)]
        completed = len(clauses) - len(pending)
        quota_wait_used = False
        for start in range(0, len(pending), 25):
            group = pending[start:start + 25]
            texts = [f"{c.label} {c.title}\n{c.text}" for c in group]
            try:
                vectors = embed_texts(texts, "RETRIEVAL_DOCUMENT")
            except ClientError as exc:
                # The SDK has already tried short backoff. Give one quota window
                # to reset, only if time remains for facts within Cloud Run's limit.
                if exc.code != 429 or quota_wait_used or time.monotonic() - started_at > 120:
                    raise
                quota_wait_used = True
                store.save_policy(doc_id, {'processingStage': 'waiting_for_embedding_quota'})
                time.sleep(60)
                store.save_policy(doc_id, {'processingStage': stage})
                vectors = embed_texts(texts, "RETRIEVAL_DOCUMENT")
            if len(vectors) != len(group):
                raise RuntimeError("Policy indexing returned an incomplete result")
            # Save each successful batch before the next Google call can fail.
            store.save_clauses(doc_id, group, vectors)
            completed += len(group)
            store.save_policy(doc_id, {'indexedClauseCount': completed})

        stage = "extracting_facts"
        store.save_policy(doc_id, {"processingStage": stage})
        facts = build_policy_facts(doc_id, extract_policy_facts(pages), pages)
        # baseFacts = document facts; personal details stay in the guest session.
        store.save_policy(doc_id, {"status": "ready", "processingStage": "ready", "lastErrorCode": None,
                                   "baseFacts": facts.model_dump(), "facts": facts.model_dump(), "clauseCount": len(clauses)})
        store.set_active_policy(doc_id)
        return UploadResult(detectedType="Policy document", pages=len(pages), policyId=doc_id)
    except Exception as exc:
        code = getattr(exc, "code", None)
        code = code if isinstance(code, int) else None
        # Deliberately omit exception messages, document text and guest identity.
        log.warning("Policy ingestion failed stage=%s error=%s code=%s", stage, type(exc).__name__, code)
        try:
            store.save_policy(doc_id, {"status": "failed", "processingStage": stage, "lastErrorCode": code})
        except Exception:
            log.warning("Could not save policy failure status")
        raise
