"""Runs eval/golden_questions.jsonl against a running CareNest API and reports verdict + citation accuracy.

Usage:  python eval/run_policy_eval.py http://localhost:8000
        python eval/run_policy_eval.py https://carenest-xxxx.a.run.app
Upload the demo policy first (demo-data/sample_policy.pdf). Standard library only.
"""
import json
import sys
import urllib.request
from pathlib import Path

GOLDEN = Path(__file__).resolve().parent / "golden_questions.jsonl"


def ask(base_url: str, question: str) -> dict:
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/copilot/ask",
        data=json.dumps({"question": question}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.load(resp)["answer"]


def main() -> None:
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    cases = [json.loads(line) for line in GOLDEN.read_text(encoding="utf-8").splitlines() if line.strip()]
    verdict_ok = cite_ok = 0
    for case in cases:
        answer = ask(base_url, case["question"])
        pages = {c["page"] for c in answer["citations"]}
        v_ok = answer["verdict"] in case["expected_verdicts"]
        # Questions with no expected pages pass only when nothing is cited (no invented sources).
        c_ok = bool(pages & set(case["expected_pages"])) if case["expected_pages"] else not pages
        verdict_ok += v_ok
        cite_ok += c_ok
        mark = "PASS" if v_ok and c_ok else "FAIL"
        print(f"[{mark}] {case['question']}\n       verdict={answer['verdict']} pages={sorted(pages)} "
              f"(expected {case['expected_verdicts']} pages {case['expected_pages']})")
    n = len(cases)
    print(f"\nVerdict accuracy: {verdict_ok}/{n} ({verdict_ok / n:.0%})   Citation accuracy: {cite_ok}/{n} ({cite_ok / n:.0%})")


if __name__ == "__main__":
    main()
