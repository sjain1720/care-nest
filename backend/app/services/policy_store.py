"""Firestore layout for policies:

policies/{policyId}                 status, filename, pageCount, facts (PolicyFacts), clauseCount
policies/{policyId}/pages/{NNN}     page, text
policies/{policyId}/clauses/{id}    page, label, title, text, embedding (768-dim vector)
app/state                           activePolicyId (single demo user)
"""
from google.cloud import firestore
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from google.cloud.firestore_v1.vector import Vector

from app.core.gcp import bucket, db
from app.services.clauses import Clause

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


def load_pages(policy_id: str) -> dict[int, str]:
    return {d.get("page"): d.get("text") for d in _policy(policy_id).collection("pages").stream()}


def save_clauses(policy_id: str, clauses: list[Clause], vectors: list[list[float]]) -> None:
    col = _policy(policy_id).collection("clauses")
    _write_in_batches([
        (col.document(c.clause_id),
         {"page": c.page, "label": c.label, "title": c.title, "text": c.text, "embedding": Vector(v)})
        for c, v in zip(clauses, vectors)
    ])


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
        hits.append({"id": snap.id, **d})
    return hits


def set_active_policy(policy_id: str) -> None:
    db().collection("app").document("state").set({"activePolicyId": policy_id}, merge=True)


def get_active_policy_id() -> str | None:
    snap = db().collection("app").document("state").get()
    return (snap.to_dict() or {}).get("activePolicyId") if snap.exists else None
