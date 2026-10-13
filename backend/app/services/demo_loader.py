"""Loads the synthetic demo case through the REAL pipeline (Document AI, embeddings, Gemini), so anyone can try live AI
without their own documents. Files that were already processed are reused, so repeat clicks cost nothing."""
from pathlib import Path

from app.services import policy_store
from app.services.policy_ingest import process_upload, ingest_policy

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
    """Loads the demo into this guest's session; the schedule details go into the session, not the shared policy."""
    folder = _demo_dir()
    results = []
    for name, doc_type in _FILES:
        data = (folder / name).read_bytes()
        r = ingest_policy(data, name, shared_demo=True) if doc_type == "Policy document" else process_upload(data, name, doc_type)
        if doc_type == "Policy document" and r.policyId:
            policy_store.save_session_details(DEMO_DETAILS)
        results.append({"file": name, "type": r.detectedType, "pages": r.pages, "reused": r.reused, "message": r.message})
    return results
