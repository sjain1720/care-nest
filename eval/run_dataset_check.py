"""Uploads every policy PDF in a folder to a running CareNest API and reports how well extraction worked.

Usage:  python eval/run_dataset_check.py http://localhost:8000 "path/to/policies/test data"
Policy wordings only - never run this on bills or other files with personal data. Standard library only.
"""
import json
import sys
import urllib.request
import uuid
from pathlib import Path

UNVERIFIED = "We couldn't find the exact wording"
# Keeps the guest-session cookie, so the policy read back is the one just uploaded.
_OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())


def upload(base_url: str, pdf: Path) -> dict:
    boundary = uuid.uuid4().hex
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{pdf.name}\"\r\n"
            f"Content-Type: application/pdf\r\n\r\n").encode() + pdf.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(f"{base_url}/api/documents", data=body, method="POST",
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with _OPENER.open(req, timeout=600) as resp:
        return json.load(resp)


def get_policy(base_url: str) -> dict:
    with _OPENER.open(f"{base_url}/api/policy", timeout=60) as resp:
        return json.load(resp)


def citations(f: dict) -> list:
    out = [f[k]["citation"] for k in ("roomRent", "coPay", "deductible") if f.get(k, {}).get("citation")]
    out += [s["citation"] for s in f.get("subLimits", []) if s.get("citation")]
    out += [w["citation"] for w in f.get("waitingPeriods", [])] + [t["citation"] for t in f.get("traps", [])]
    return out


def main() -> None:
    base_url = sys.argv[1].rstrip("/")
    folder = Path(sys.argv[2])
    total_cites = total_unverified = 0
    print(f"{'file':40} {'pages':>5} {'type':17} {'start':5} {'SI':4} {'room':5} {'WPs':>3} {'traps':>5} {'quotes ok':>10}")
    for pdf in sorted(folder.glob("*.pdf")):
        try:
            result = upload(base_url, pdf)
            if result.get("detectedType") != "Policy document":
                print(f"{pdf.name[:40]:40} {result.get('pages', 0):>5} detected as {result.get('detectedType')}")
                continue
            f = get_policy(base_url)
        except Exception as exc:  # report and continue with the next file
            print(f"{pdf.name[:40]:40} ERROR {exc}")
            continue
        cites = len(citations(f))
        unverified = sum(1 for fl in f["flags"] if fl["message"].startswith(UNVERIFIED))
        total_cites += cites
        total_unverified += unverified
        yes = lambda v: "yes" if v else "-"  # noqa: E731
        print(f"{pdf.name[:40]:40} {f['pageCount']:>5} {f.get('productType', '?'):17} {yes(f['startDate']):5} "
              f"{yes(f['sumInsured']):4} {yes(f['roomRent'].get('amount')):5} {len(f['waitingPeriods']):>3} "
              f"{len(f['traps']):>5} {cites - unverified:>4}/{cites:<5}")
    if total_cites:
        print(f"\nQuotes verified against the document: {total_cites - total_unverified}/{total_cites} "
              f"({(total_cites - total_unverified) / total_cites:.0%})")
    print("Note: the last uploaded policy is now the active one in the app.")


if __name__ == "__main__":
    main()
