"""Runs eval/golden_questions.jsonl against a running CareNest API and reports verdict + citation accuracy.

Usage:  python eval/run_policy_eval.py http://localhost:8000
        python eval/run_policy_eval.py https://carenest-xxxx.a.run.app
Uploads the demo policy and its schedule details first, in this script's own guest session. Standard library only.
"""
import json
import sys
import urllib.request
import uuid
from pathlib import Path

GOLDEN = Path(__file__).resolve().parent / "golden_questions.jsonl"
DEMO_POLICY = Path(__file__).resolve().parents[1] / "demo-data" / "sample_policy.pdf"
# Same schedule details as backend/app/services/demo_loader.py (the demo PDF is a wording without a schedule).
DEMO_DETAILS = {
    "startDate": "2024-03-12", "sumInsured": 500000, "roomRentPerDay": 5000, "policyNumber": "XXXX-XXXX-4821",
    "members": [{"name": "Ravi Sharma", "relation": "Self", "age": 32}, {"name": "Mohan Sharma", "relation": "Father", "age": 62},
                {"name": "Kamala Sharma", "relation": "Mother", "age": 58}],
}
# Keeps the guest-session cookie, so every call below sees the same uploaded policy.
_OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())


def setup_demo_policy(base_url: str) -> None:
    boundary = uuid.uuid4().hex
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"docType\"\r\n\r\nPolicy document\r\n"
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"sample_policy.pdf\"\r\n"
            f"Content-Type: application/pdf\r\n\r\n").encode() + DEMO_POLICY.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    _OPENER.open(urllib.request.Request(f"{base_url}/api/documents", data=body, method="POST",
                                        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}), timeout=600).read()
    _OPENER.open(urllib.request.Request(f"{base_url}/api/policy/details", data=json.dumps(DEMO_DETAILS).encode(), method="PUT",
                                        headers={"Content-Type": "application/json"}), timeout=60).read()


def ask(base_url: str, question: str) -> dict:
    req = urllib.request.Request(
        f"{base_url}/api/copilot/ask",
        data=json.dumps({"question": question}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with _OPENER.open(req, timeout=120) as resp:
        return json.load(resp)["answer"]


def main() -> None:
    base_url = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
    setup_demo_policy(base_url)
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
