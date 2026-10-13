"""Evaluate a live demo with resumable results and bounded transient retries."""
import argparse
import json
import time
from pathlib import Path

import requests


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("output", type=Path)
    parser.add_argument("--model", required=True)
    args = parser.parse_args()
    golden = [json.loads(line) for line in (Path(__file__).parent / "golden_questions.jsonl").read_text().splitlines() if line.strip()]
    report = {"url": args.url, "model": args.model, "cases": [], "completed": False}
    if args.output.exists():
        report = json.loads(args.output.read_text())
        if report["model"] != args.model or report["url"] != args.url:
            raise ValueError("Report belongs to a different deployment")
    session = requests.Session()
    loaded = session.post(args.url.rstrip('/') + '/api/demo/load', timeout=300)
    loaded.raise_for_status()
    completed = {row["question"] for row in report["cases"]}
    for case in golden:
        if case["question"] in completed:
            continue
        for attempt in range(3):
            try:
                response = session.post(args.url.rstrip("/") + "/api/copilot/ask",
                                         json={"question": case["question"]}, timeout=150)
                response.raise_for_status()
                answer = response.json()["answer"]
                break
            except (requests.Timeout, requests.ConnectionError, requests.HTTPError):
                if attempt == 2:
                    raise
                time.sleep(15 * (attempt + 1))
        pages = {citation["page"] for citation in answer["citations"]}
        report["cases"].append({"question": case["question"], "answer": answer,
            "verdictOk": answer["verdict"] in case["expected_verdicts"],
            "citationOk": bool(pages & set(case["expected_pages"])) if case["expected_pages"] else not pages})
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2))
        print(case["question"], answer["verdict"], sorted(pages), flush=True)
        time.sleep(7)
    report.update({"completed": True, "verdictPass": sum(r["verdictOk"] for r in report["cases"]),
                   "citationPass": sum(r["citationOk"] for r in report["cases"]), "total": len(golden)})
    args.output.write_text(json.dumps(report, indent=2))
    session.delete(args.url.rstrip("/") + "/api/session", timeout=60).raise_for_status()
    print({k: v for k, v in report.items() if k != "cases"})


if __name__ == "__main__":
    main()
