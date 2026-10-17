"""Firestore layout for policies:

policies/{policyId}                 status, filename, pageCount, baseFacts (what the document says), clauseCount
policies/{policyId}/pages/{NNN}     page, text
policies/{policyId}/clauses/{id}    page, label, title, text, embedding (768-dim vector)
sessions/{sessionId}                activePolicyId, policyDetails (schedule details this guest typed in), expireAt

Private policy documents are scoped by guest and hash. Only synthetic demo wordings are shared.
Personal schedule details live only in the guest session.
"""
import hashlib

from google.cloud import firestore
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from google.cloud.firestore_v1.vector import Vector

from app.core.gcp import bucket, db
from app.core.config import get_settings
from app.core.session import expiry, session_id
from app.services.clauses import Clause
from app.services.policy_details import apply_user_details

_BATCH_LIMIT = 400


def _policy(policy_id: str):
    return db().collection("policies").document(policy_id)


def original_blob_name(policy_id: str) -> str:
    return f"policies/{policy_id}/original.pdf"


def get_policy(policy_id: str) -> dict | None:
    snap = _policy(policy_id).get()
    return snap.to_dict() if snap.exists else None


def save_policy(policy_id: str, data: dict) -> None:
    _policy(policy_id).set({**data, "updatedAt": firestore.SERVER_TIMESTAMP}, merge=True)


def save_original(policy_id: str, pdf_bytes: bytes) -> None:
    bucket().blob(original_blob_name(policy_id)).upload_from_string(pdf_bytes, content_type="application/pdf")


def load_original(policy_id: str) -> bytes:
    return bucket().blob(original_blob_name(policy_id)).download_as_bytes()


def _write_in_batches(items: list[tuple]) -> None:
    for i in range(0, len(items), _BATCH_LIMIT):
        batch = db().batch()
        for ref, data in items[i:i + _BATCH_LIMIT]:
            batch.set(ref, data)
        batch.commit()


def save_pages(policy_id: str, pages: list[dict]) -> None:
    col = _policy(policy_id).collection("pages")
    _write_in_batches([(col.document(f"{p['page']:03d}"), {"page": p["page"], "text": p["text"]}) for p in pages])


def load_page(policy_id: str, page: int) -> str | None:
    value = _policy(policy_id).collection('pages').document(f'{page:03d}').get().to_dict() or {}
    return value.get('text')


def load_pages(policy_id: str) -> dict[int, str]:
    return {d.get("page"): d.get("text") for d in _policy(policy_id).collection("pages").stream()}


def save_clauses(policy_id: str, clauses: list[Clause], vectors: list[list[float]]) -> None:
    if len(clauses) != len(vectors):
        raise ValueError('Cannot save an incomplete embedding batch')
    col = _policy(policy_id).collection("clauses")
    _write_in_batches([
        (col.document(c.clause_id),
         {"page": c.page, "label": c.label, "title": c.title, "text": c.text, "embedding": Vector(v), **clause_index_stamp(c)})
        for c, v in zip(clauses, vectors)
    ])


def clause_index_stamp(clause: Clause) -> dict:
    text = f'{clause.label} {clause.title}\n{clause.text}'
    return {'embeddingModel': get_settings().embedding_model,
            'embeddingTextHash': hashlib.sha256(text.encode()).hexdigest()}


def load_clause_index(policy_id: str) -> dict:
    """Resume only atomically saved batches with matching text and encoder."""
    rows = _policy(policy_id).collection('clauses').select(['embeddingModel', 'embeddingTextHash']).stream()
    return {row.id: row.to_dict() for row in rows}


def search_clauses(policy_id: str, query_vector: list[float], k: int = 6) -> list[dict]:
    results = (
        _policy(policy_id).collection("clauses")
        .find_nearest(vector_field="embedding", query_vector=Vector(query_vector),
                      distance_measure=DistanceMeasure.COSINE, limit=k, distance_result_field="distance")
        .get()
    )
    hits = []
    for snap in results:
        d = snap.to_dict()
        d.pop("embedding", None)
        d.pop('embeddingModel', None)
        d.pop('embeddingTextHash', None)
        hits.append({"id": snap.id, **d})
    return hits


def _session():
    return db().collection("sessions").document(session_id())


def _session_state() -> dict:
    snap = _session().get()
    return (snap.to_dict() or {}) if snap.exists else {}


def _save_session_state(data: dict) -> None:
    _session().set({**data, "updatedAt": firestore.SERVER_TIMESTAMP, "expireAt": expiry()}, merge=True)


def set_active_policy(policy_id: str) -> None:
    """A new policy for this guest: earlier typed-in details belonged to the old one, so they are cleared."""
    state = _session_state()
    if state.get("activePolicyId") != policy_id:
        _save_session_state({"activePolicyId": policy_id, "policyDetails": firestore.DELETE_FIELD})
    else:
        _save_session_state({"activePolicyId": policy_id})


def get_active_policy_id() -> str | None:
    return _session_state().get("activePolicyId")


def save_session_details(details: dict) -> None:
    _save_session_state({"policyDetails": details})


def get_active_policy() -> tuple[str, dict] | None:
    """This guest's ready policy; its "facts" are the document's facts plus the details this guest typed in."""
    state = _session_state()
    policy_id = state.get("activePolicyId")
    doc = get_policy(policy_id) if policy_id else None
    if not doc or doc.get("status") != "ready":
        return None
    base = doc.get("baseFacts") or doc["facts"]
    details = state.get("policyDetails")
    # Old visitor copies of our fictional schedule keep the current demo name.
    # Never rename people in a visitor's uploaded private policy.
    if doc.get("isDemoTemplate") and details and isinstance(details.get("members"), list):
        details = {**details, "members": [
            {**member, "name": "Shubham Sharma"} if member.get("name") == "Ravi Sharma" else member
            for member in details["members"]
        ]}
    facts = apply_user_details(base, details) if details else base
    if doc.get('isDemoTemplate') and state.get('demoAssumptions'):
        from app.services.demo_profile import apply_demo_selections
        facts = apply_demo_selections(facts, state['demoAssumptions'])
        from app.services.session_profile import get_display_name
        name = get_display_name()
        if name:
            facts = {**facts, 'members': [{**m, 'name': name} if m.get('relation') == 'Self' else m for m in facts.get('members', [])]}
    return policy_id, {**doc, "facts": facts}


def delete_session_state() -> None:
    _session().delete()
