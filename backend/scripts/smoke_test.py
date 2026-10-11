"""Phase 0 connection test. Run from backend/:  python -m scripts.smoke_test [path\\to\\policy.pdf]"""
import sys
from pathlib import Path

from app.core.config import get_settings
from app.core.gcp import bucket, db, gemini
from app.services.ocr import ocr_pdf


def run(name, fn):
    try:
        print(f"[PASS] {name}: {fn()}")
        return True
    except Exception as exc:
        print(f"[FAIL] {name}: {type(exc).__name__}: {exc}")
        return False


def main():
    s = get_settings()
    print(f"Project {s.project_id} | Gemini location {s.gemini_location} | Document AI {s.docai_location}\n")

    results = [
        run("Gemini", lambda: gemini().models.generate_content(
            model=s.gemini_model, contents="Explain co-payment in one simple line.").text.strip()),
        run("Embeddings", lambda: f"{len(gemini().models.embed_content(model=s.embedding_model, contents='Room rent is capped at 1% of sum insured').embeddings[0].values)} dimensions"),
        run("Firestore", lambda: (db().collection("healthcheck").document("ping").set({"ok": True}),
                                  db().collection("healthcheck").document("ping").get().to_dict())[1]),
        run("Cloud Storage", lambda: f"bucket exists = {bucket().exists()}"),
    ]

    if len(sys.argv) > 1:
        pdf = Path(sys.argv[1])
        def ocr():
            pages = ocr_pdf(pdf.read_bytes())
            numbers = [p["page"] for p in pages]
            return f"{len(pages)} pages (first {numbers[0]}, last {numbers[-1]}); page 1 starts: {pages[0]['text'][:120]!r}"
        results.append(run(f"Document AI OCR ({pdf.name})", ocr))
    else:
        print("[SKIP] Document AI OCR: pass a PDF path to test it")

    print("\nAll checks passed." if all(results) else "\nSome checks failed - see messages above.")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
