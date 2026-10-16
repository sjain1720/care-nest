"""Index prepared policy evidence without replacing the app's active demo policy."""
import argparse
import json
import time
from pathlib import Path

from google.cloud.firestore_v1.vector import Vector
from google.genai.errors import ClientError

from app.core.gcp import bucket, db
from app.services.embeddings import embedding_batches, embed_texts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("dataset", type=Path)
    args = parser.parse_args()
    manifests = json.loads((args.corpus / "manifest.json").read_text())
    pages = [json.loads(line) for line in (args.corpus / "pages.jsonl").read_text().splitlines()]
    clauses = [json.loads(line) for line in (args.corpus / "clauses.jsonl").read_text().splitlines()]
    for item in manifests:
        policy_id = item["policyId"]
        ref = db().collection("trainingPolicies").document(policy_id)
        existing = ref.get().to_dict() or {}
        if existing.get("status") == "indexed" and existing.get("sha256") == item["sha256"]:
            print(f"Reused {item['filename']}", flush=True)
            continue
        content = (args.dataset / item["filename"]).read_bytes()
        import hashlib
        if hashlib.sha256(content).hexdigest() != item["sha256"]:
            raise ValueError(f"Source PDF changed: {item['filename']}; regenerate corpus")
        selected_pages = [p for p in pages if p["policyId"] == policy_id]
        selected_clauses = [c for c in clauses if c["policyId"] == policy_id]
        texts = [f"{c['label']} {c['title']}\n{c['text']}" for c in selected_clauses]
        vectors = []
        # Pace bulk preparation for projects with low per-model request quotas.
        for group in embedding_batches(texts):
            for attempt in range(5):
                try:
                    vectors.extend(embed_texts(group, "RETRIEVAL_DOCUMENT"))
                    break
                except ClientError as exc:
                    if exc.code != 429 or attempt == 4:
                        raise
                    print(f"Embedding quota retry in {30 * (attempt + 1)} seconds", flush=True)
                    time.sleep(30 * (attempt + 1))
            time.sleep(7)
        if len(vectors) != len(selected_clauses):
            raise ValueError("Embedding count mismatch")
        blob_name = f"training/policies/{policy_id}/original.pdf"
        bucket().blob(blob_name).upload_from_string(content, content_type="application/pdf")
        ref.set({**item, "status": "indexing", "originalBlob": blob_name})
        records = [(ref.collection("pages").document(str(p["page"])), p) for p in selected_pages]
        records += [(ref.collection("clauses").document(c["clause_id"]), {**c, "embedding": Vector(v)})
                    for c, v in zip(selected_clauses, vectors)]
        for start in range(0, len(records), 400):
            batch = db().batch()
            for doc, data in records[start:start + 400]:
                batch.set(doc, data)
            batch.commit()
        ref.update({"status": "indexed"})
        print(f"Indexed {item['filename']}: {len(selected_pages)} pages, {len(vectors)} vectors", flush=True)


if __name__ == "__main__":
    main()
