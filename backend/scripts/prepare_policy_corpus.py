"""Prepare page-preserving policy evidence locally; never creates training labels."""
import argparse
import hashlib
import json
from pathlib import Path

from pypdf import PdfReader

from app.services.clauses import split_into_clauses

SELECTED = (
    "HDFHLGP22144V032122_HEALTH2096.pdf",
    "ICIHLGP23027V012223.pdf",
    "Kotak Group Health Assure.pdf",
    "NAVHLIP23003V012223.pdf",
    "SHAHLGP23015V012223.pdf",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    # Validate all selected inputs before writing any output.
    paths = [args.dataset / name for name in SELECTED]
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(path)
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = []
    with (args.output / "pages.jsonl").open("w") as page_file, (args.output / "clauses.jsonl").open("w") as clause_file:
        for path in paths:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            policy_id = "pol-" + digest[:16]
            pages = [{"page": n, "text": page.extract_text() or ""}
                     for n, page in enumerate(PdfReader(path).pages, 1)]
            clauses = split_into_clauses(pages)
            for page in pages:
                page_file.write(json.dumps({"policyId": policy_id, "filename": path.name, **page}, ensure_ascii=False) + "\n")
            for clause in clauses:
                clause_file.write(json.dumps({"policyId": policy_id, "filename": path.name, **vars(clause)}, ensure_ascii=False) + "\n")
            manifest.append({"policyId": policy_id, "filename": path.name, "sha256": digest,
                             "pages": len(pages), "clauses": len(clauses),
                             "characters": sum(len(p["text"]) for p in pages),
                             "needsReviewPages": [p["page"] for p in pages if len(p["text"].strip()) < 100]})
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"policies": len(manifest), "pages": sum(p["pages"] for p in manifest),
                      "clauses": sum(p["clauses"] for p in manifest), "output": str(args.output.resolve())}, indent=2))


if __name__ == "__main__":
    main()
