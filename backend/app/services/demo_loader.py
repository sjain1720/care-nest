"""Loads the synthetic demo case through the REAL pipeline (Document AI, embeddings, Gemini), so anyone can try live AI
without their own documents. Files that were already processed are reused, so repeat clicks cost nothing."""
from pathlib import Path

from app.schemas import PolicyFacts
from app.services import policy_store
from app.services.policy_details import apply_user_details
from app.services.policy_ingest import process_upload

_APP = Path(__file__).resolve().parents[1]
# Container: the Angular build copies public/demo into static/demo. Local/Cloud Shell: the repo's demo-data folder.
_DEMO_DIRS = [_APP.parent / "static" / "demo", _APP.parents[1] / "demo-data"]

# Matches the synthetic policy schedule (the demo PDF is a wording without a schedule).
DEMO_DETAILS = {
    "startDate": "2024-03-12", "sumInsured": 500000, "roomRentPerDay": 5000, "policyNumber": "XXXX-XXXX-4821",
    "members": [{"name": "Ravi Sharma", "relation": "Self", "age": 32}, {"name": "Mohan Sharma", "relation": "Father", "age": 62},
                {"name": "Kamala Sharma", "relation": "Mother", "age": 58}],
}
_FILES = (("sample_policy.pdf", "Policy document"), ("hospital_bill.pdf", "Hospital bill"), ("settlement_letter.pdf", "Settlement letter"))


def _demo_dir() -> Path:
    for d in _DEMO_DIRS:
        if all((d / name).exists() for name, _ in _FILES):
            return d
    raise FileNotFoundError("Demo PDFs not found. Run: python demo-data/make_demo_pdfs.py")


def load_demo_case() -> list[dict]:
    folder = _demo_dir()
    results = []
    for name, doc_type in _FILES:
        r = process_upload((folder / name).read_bytes(), name, doc_type)
        if doc_type == "Policy document" and r.policyId:
            doc = policy_store.get_policy(r.policyId)
            facts = PolicyFacts.model_validate(apply_user_details(doc.get("baseFacts") or doc["facts"], DEMO_DETAILS))
            policy_store.save_policy(r.policyId, {"userDetails": DEMO_DETAILS, "facts": facts.model_dump()})
        results.append({"file": name, "type": r.detectedType, "pages": r.pages, "reused": r.reused, "message": r.message})
    return results
