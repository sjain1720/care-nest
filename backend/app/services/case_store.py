"""Firestore + Storage for each guest's claims.

cases/{sessionId}                         the claim being worked on: documents[], billHeader{}, bill{}, billExtraction{}, settlement{},
                                          rejection{}, timeline[], expireAt   (structured data only – raw bill text is never stored)
cases/{sessionId}/pastClaims/{claimId}    earlier claims: summary{}, case{} (kept CareNest claims only), expireAt
Storage                                   cases/{sessionId}/doc-….pdf and img-… (photos)   (shared by all of the guest's claims)
"""
from contextlib import contextmanager
from contextvars import ContextVar
import re

from google.api_core.exceptions import NotFound
from google.cloud import firestore

from app.core.gcp import bucket, db
from app.core.session import expiry, session_id
from app.services.claim_financials import effective_case
from app.services.claim_history import archived_summary, has_content, new_claim_id, summarize_case

DOC_ID = re.compile(r"^(doc|img)-[0-9a-f]{16}$")
_META_KEYS = ("id", "updatedAt", "expireAt")


def _case():
    return db().collection("cases").document(session_id())


def _past():
    return _case().collection("pastClaims")


def _blob(doc_id: str):
    return bucket().blob(f"cases/{session_id()}/{doc_id}" + (".pdf" if doc_id.startswith("doc-") else ""))


def get_case() -> dict:
    snap = _case().get()
    return effective_case({"id": "current", **(snap.to_dict() or {})}) if snap.exists else {"id": "current"}


def update_case(data: dict) -> None:
    if _expected_flow.get():
        def update(current):
            check_flow(current)
            return data
        mutate_case(update)
    else:
        _case().set({**data, "updatedAt": firestore.SERVER_TIMESTAMP, "expireAt": expiry()}, merge=True)


def add_document(doc: dict) -> None:
    if _expected_flow.get():
        def append(current):
            check_flow(current)
            return {'documents': [d for d in current.get('documents', []) if d['id'] != doc['id']] + [doc]}
        mutate_case(append)
        return
    current = [d for d in get_case().get("documents", []) if d["id"] != doc["id"]]
    update_case({"documents": current + [doc]})


def add_timeline_event(event: dict) -> None:
    if _expected_flow.get():
        def append(current):
            check_flow(current)
            return {'timeline': current.get('timeline', []) + [event]}
        mutate_case(append)
        return
    update_case({"timeline": (get_case().get("timeline") or []) + [event]})


def remove_timeline_event(event_id: str) -> bool:
    events = get_case().get("timeline") or []
    kept = [e for e in events if e.get("id") != event_id]
    if len(kept) == len(events):
        return False
    update_case({"timeline": kept})
    return True


def save_file(doc_id: str, data: bytes, mime: str) -> None:
    if _expected_flow.get():
        check_flow(get_case())
    _blob(doc_id).upload_from_string(data, content_type=mime)


def load_file(doc_id: str) -> tuple[bytes, str]:
    """The uploaded file and its type (PDF or photo)."""
    if not DOC_ID.match(doc_id):
        raise ValueError("Invalid document id")
    blob = bucket().get_blob(_blob(doc_id).name)
    if blob is None:
        raise NotFound("Document not found")
    return blob.download_as_bytes(), blob.content_type or "application/pdf"


def _archive(batch, case: dict) -> None:
    """Adds the claim being worked on to the earlier claims, files and all, so it can be opened again."""
    claim_id = new_claim_id()
    snapshot = {k: v for k, v in case.items() if k not in _META_KEYS}
    batch.set(_past().document(claim_id), {"summary": summarize_case(case, claim_id), "case": snapshot, "expireAt": expiry()})


def list_past_claims() -> list[dict]:
    return [archived_summary(snap.to_dict()) for snap in _past().stream()]


def get_past_claim(claim_id: str) -> dict | None:
    snap = _past().document(claim_id).get()
    return snap.to_dict() if snap.exists else None


def add_past_claim(summary: dict) -> None:
    _past().document(summary["id"]).set({"summary": summary, "expireAt": expiry()})


def start_new_claim() -> None:
    """Keeps the current claim in the list of earlier claims and starts an empty one."""
    case = get_case()
    batch = db().batch()
    if has_content(case):
        _archive(batch, case)
    batch.delete(_case())
    batch.commit()


def open_past_claim(claim_id: str, case_snapshot: dict) -> None:
    """Makes an earlier claim the one being worked on; the current claim moves into the list."""
    current = get_case()
    batch = db().batch()
    if has_content(current):
        _archive(batch, current)
    batch.set(_case(), {**case_snapshot, "updatedAt": firestore.SERVER_TIMESTAMP, "expireAt": expiry()})
    batch.delete(_past().document(claim_id))
    batch.commit()


def delete_past_claim(claim_id: str, past: dict) -> None:
    """Deletes an earlier claim and its files, keeping any file another claim also uses."""
    _past().document(claim_id).delete()
    in_use = {d["id"] for d in get_case().get("documents", [])}
    for snap in _past().stream():
        in_use |= {d["id"] for d in (snap.to_dict().get("case") or {}).get("documents", [])}
    for doc in (past.get("case") or {}).get("documents", []):
        if doc["id"] not in in_use:
            try:
                _blob(doc["id"]).delete()
            except NotFound:
                pass  # already removed by the bucket's 7-day rule


def delete_case() -> None:
    """Removes every claim of this guest and every claim file they uploaded."""
    for blob in bucket().list_blobs(prefix=f"cases/{session_id()}/"):
        blob.delete()
    for snap in _past().stream():
        snap.reference.delete()
    _case().delete()


def mutate_case(change):
    """Apply a small owned-case mutation transactionally; callers validate context."""
    client = db()
    ref = _case()
    @firestore.transactional
    def apply(transaction):
        snap = ref.get(transaction=transaction)
        current = snap.to_dict() or {}
        patch = change(current)
        if patch:
            transaction.set(ref, {**patch, 'updatedAt': firestore.SERVER_TIMESTAMP, 'expireAt': expiry()}, merge=True)
        return {**current, **patch}
    return apply(client.transaction())


_expected_flow = ContextVar('expected_case_flow', default=None)


@contextmanager
def guard_flow(identity):
    token = _expected_flow.set(identity)
    try:
        yield
    finally:
        _expected_flow.reset(token)


def check_flow(current):
    expected = _expected_flow.get()
    if expected and current.get('flowId') != expected:
        from app.services.claim_flow import FlowConflict
        raise FlowConflict('The selected claim changed during processing. Return to documents and retry in the correct claim.')
