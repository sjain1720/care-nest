"""Verify stored source bytes, page counts, vectors and real semantic retrieval."""
import argparse
import hashlib
import json
from pathlib import Path

from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from google.cloud.firestore_v1.vector import Vector

from app.core.gcp import bucket, db
from app.services.embeddings import embed_texts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path)
    args = parser.parse_args()
    manifests = json.loads((args.corpus / "manifest.json").read_text())
    query = embed_texts(["What are the waiting periods and exclusions for cataract treatment?"], "RETRIEVAL_QUERY")[0]
    for item in manifests:
        ref = db().collection("trainingPolicies").document(item["policyId"])
        metadata = ref.get().to_dict() or {}
        if metadata.get("status") != "indexed":
            raise ValueError(f"Not indexed: {item['filename']}")
        source = bucket().blob(metadata["originalBlob"]).download_as_bytes()
        if hashlib.sha256(source).hexdigest() != item["sha256"]:
            raise ValueError("Stored source checksum mismatch")
        pages = list(ref.collection("pages").stream())
        clauses = list(ref.collection("clauses").stream())
        if len(pages) != item["pages"] or len(clauses) != item["clauses"]:
            raise ValueError("Stored page/clause count mismatch")
        hits = ref.collection("clauses").find_nearest(
            vector_field="embedding", query_vector=Vector(query), limit=3,
            distance_measure=DistanceMeasure.COSINE).get()
        if not hits:
            raise ValueError("No retrieval results")
        print(json.dumps({"filename": item["filename"], "sourceVerified": True,
                          "pages": len(pages), "clauses": len(clauses),
                          "retrievedPages": [hit.to_dict()["page"] for hit in hits]}), flush=True)


if __name__ == "__main__":
    main()
