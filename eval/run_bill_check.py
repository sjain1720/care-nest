"""Uploads every bill PDF in a folder to a running CareNest API and prints what the bill checks found.

Usage:  python eval/run_bill_check.py http://localhost:8000 "path/to/medical-bills"
Real bills contain personal data: run this only against YOUR OWN private project, and only if the dataset's terms allow it.
The output shows no names - only counts, totals and check results. Standard library only.
"""
import json
import sys
import urllib.request
import uuid
from pathlib import Path


def upload(base_url: str, pdf: Path) -> dict:
    boundary = uuid.uuid4().hex
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"docType\"\r\n\r\nHospital bill\r\n"
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{pdf.name}\"\r\n"
            f"Content-Type: application/pdf\r\n\r\n").encode() + pdf.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(f"{base_url}/api/documents", data=body, method="POST",
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=600) as resp:
        return json.load(resp)


def get_bill(base_url: str) -> dict:
    with urllib.request.urlopen(f"{base_url}/api/case/bill", timeout=60) as resp:
        return json.load(resp)


def main() -> None:
    base_url, folder = sys.argv[1].rstrip("/"), Path(sys.argv[2])
    print(f"{'file':32} {'pages':>9} {'items':>5} {'total':>12} {'not payable?':>12}  checks")
    for pdf in sorted(folder.glob("*.pdf")):
        if "merged" in pdf.name:
            continue  # merged files repeat the single bills
        try:
            upload(base_url, pdf)
            b = get_bill(base_url)
        except Exception as exc:  # report and continue with the next file
            print(f"{pdf.name[:32]:32} ERROR {exc}")
            continue
        pages = f"{b['pagesRead']}/{b['pagesExpected'] or '?'}"
        non_pay = sum(i["amount"] for i in b["items"] if i["tag"] == "possibly_non_payable")
        kinds = ", ".join(sorted({c["kind"] for c in b["checks"]})) or "none"
        print(f"{pdf.name[:32]:32} {pages:>9} {len(b['items']):>5} {b['total']:>12,.0f} {non_pay:>12,.0f}  {kinds}")
    print("\nNote: the last uploaded bill is now the active bill in the app.")


if __name__ == "__main__":
    main()
