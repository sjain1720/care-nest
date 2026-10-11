"""Builds the synthetic demo PDFs (policy wording, settlement letter, hospital bill) with plain Python.

Run:  python demo-data/make_demo_pdfs.py
Writes to demo-data/ and frontend/public/demo/. All content is fictional – no real policy or patient data.
"""
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT_DIRS = [ROOT, ROOT.parent / "frontend" / "public" / "demo"]
BANNER = "SYNTHETIC DEMO DOCUMENT - NOT A REAL POLICY OR CLAIM"


# ---------- minimal PDF writer (built-in Helvetica, A4) ----------

def _pdf_text(s: str) -> bytes:
    s = s.replace("₹", "Rs. ").replace("–", "-").replace("’", "'").replace("“", '"').replace("”", '"')
    s = s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return s.encode("latin-1", "replace")


def _page_stream(lines: list[str], page_no: int, total: int, footer: str) -> bytes:
    out = [b"BT /F2 8 Tf 50 815 Td (" + _pdf_text(BANNER) + b") Tj ET",
           b"BT /F1 11 Tf 15 TL 50 780 Td"]
    for line in lines:
        if line.startswith("# "):
            out.append(b"/F2 14 Tf (" + _pdf_text(line[2:]) + b") Tj T* T* /F1 11 Tf")
        elif line.startswith("## "):
            out.append(b"/F2 11 Tf (" + _pdf_text(line[3:]) + b") Tj T* /F1 11 Tf")
        elif line == "":
            out.append(b"T*")
        else:
            for part in textwrap.wrap(line, 92):
                out.append(b"(" + _pdf_text(part) + b") Tj T*")
    out.append(b"ET")
    out.append(b"BT /F1 9 Tf 50 40 Td (" + _pdf_text(f"{footer}  |  Page {page_no} of {total}") + b") Tj ET")
    return b"\n".join(out)


def build_pdf(pages: list[list[str]], footer: str) -> bytes:
    n = len(pages)
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        ("<< /Type /Pages /Kids [" + " ".join(f"{5 + 2 * i} 0 R" for i in range(n)) + f"] /Count {n} >>").encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
    ]
    for i, lines in enumerate(pages):
        stream = _page_stream(lines, i + 1, n, footer)
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                    f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {6 + 2 * i} 0 R >>".encode())
        objs.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for num, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{num} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{off:010d} 00000 n \n".encode() for off in offsets)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


# ---------- document content (must match frontend/public/mocks/*.json) ----------

def policy_pages() -> list[list[str]]:
    total = 42
    pages: dict[int, list[str]] = {
        1: ["# Suraksha Health Insurance Co. (demo)", "## Family Shield Gold - Policy Wording", "",
            "Policy type: Family floater", "Sum insured: Rs. 5,00,000", "Policy number: XXXX-XXXX-4821",
            "First policy commencement date: 12 March 2024", "",
            "This document is fictional and was created for the CareNest hackathon demo."],
        2: ["# Contents", "Section 1  Definitions ............................................. 3",
            "Section 3  Room, co-payment and limits ............................ 7",
            "Section 4  Waiting periods and sub-limits ......................... 9",
            "Section 5  Proportionate deduction ............................... 11",
            "Section 7  Claims procedure ...................................... 21",
            "Annexure I   Specific illnesses with waiting period ............. 36",
            "Annexure II  Non-payable items ................................. 38"],
        3: ["# Section 1 - Definitions",
            "1.1 Hospitalisation means admission in a hospital for a minimum period of 24 consecutive hours.",
            "1.2 Sum Insured means the amount stated in the Policy Schedule, available to all insured persons together.",
            "1.3 Associated medical expenses means expenses that vary with the room category, as described in Clause 5.3."],
        7: ["# Section 3 - Room, co-payment and limits",
            "## Clause 3.2 Room rent",
            "Room, boarding and nursing expenses are payable up to 1% of the Sum Insured per day for a normal room "
            "and up to 2% of the Sum Insured per day for ICU.",
            "",
            "## Clause 3.3 Choice of room",
            "The Insured Person may choose any room. Where the room exceeds the limit in Clause 3.2, Clause 5.3 applies."],
        8: ["## Clause 3.6 Co-payment",
            "For Insured Persons aged 61 years or above at the time of admission, a co-payment of 10% shall apply "
            "on every admissible claim."],
        9: ["# Section 4 - Waiting periods",
            "## Clause 4.1 Initial waiting period",
            "Expenses for any illness contracted within 30 days from the first policy commencement date are excluded, "
            "except claims arising due to an accident.",
            "",
            "## Clause 4.2 Specific illnesses",
            "The listed conditions in Annexure I, including cataract, hernia and joint replacement, are covered only "
            "after 24 months of continuous coverage.",
            "",
            "## Clause 4.3 Pre-existing diseases",
            "Expenses related to pre-existing diseases are covered after 36 months of continuous coverage from the "
            "first policy commencement date."],
        11: ["# Section 5 - Proportionate deduction",
             "## Clause 5.3",
             "Where the room category exceeds eligibility, all associated medical expenses shall be payable in the "
             "same proportion as the eligible room rent bears to the actual room rent."],
        14: ["# Section 4 (continued) - Sub-limits",
             "## Clause 4.6 Cataract",
             "Expenses for cataract treatment are payable up to Rs. 40,000 per eye per policy year.",
             "",
             "## Clause 4.8 Ambulance",
             "Road ambulance charges are payable up to Rs. 2,000 per hospitalisation."],
        15: ["## Clause 4.9 Day-care procedures",
             "Day-care procedures listed in Annexure III are covered even if hospitalisation is less than 24 hours."],
        21: ["# Section 7 - Claims procedure",
             "## Clause 7.1 Intimation",
             "In case of emergency hospitalisation, the Company/TPA must be informed within 48 hours of admission."],
        22: ["## Clause 7.4 Documents for reimbursement",
             "The following documents shall be submitted for reimbursement claims: claim form, discharge summary, "
             "final bill, payment receipts, investigation reports, prescriptions, KYC and bank details."],
        36: ["# Annexure I - Specific illnesses (24-month waiting period)",
             "Cataract; Hernia; Joint replacement; Sinusitis; Varicose veins; Kidney stones."],
        38: ["# Annexure II - Non-payable items",
             "List I - Items for which coverage is not available: gloves, PPE kit, admission kit, "
             "registration charges, toiletries, attendant charges."],
    }
    filler = ["# General conditions (continued)",
              "This page continues the general terms of the policy. It does not change the benefits, waiting "
              "periods or limits described in Sections 3, 4 and 5."]
    return [pages.get(p, filler) for p in range(1, total + 1)]


def settlement_pages() -> list[list[str]]:
    return [
        ["# Suraksha Health Insurance Co. (demo)", "## Claim settlement letter", "",
         "Date: 20 September 2026", "Claim number: CLM-2026-0083412", "Policy number: XXXX-XXXX-4821",
         "Patient: Kamala Sharma", "Hospital: City Care Hospital, Pune (demo)", "Admission: 18 Aug 2026  Discharge: 22 Aug 2026", "",
         "Amount claimed: Rs. 2,46,000", "Amount approved: Rs. 2,08,000", "Total deductions: Rs. 38,000", "",
         "The deductions are listed on page 2."],
        ["## Deductions", "",
         "1. Room-rent and proportionate deduction - Rs. 21,600",
         "   Remark: Room category exceeds eligibility. Proportionate deduction applied as per policy.",
         "2. Non-payable consumables - Rs. 6,900",
         "   Remark: Non-medical items not payable as per Annexure II.",
         "3. Other deductions: Rs. 9,500",
         "   Remark: -", "",
         "Total deductions: Rs. 38,000", "",
         "If you disagree with this settlement, you may write to our Grievance Officer."],
    ]


def bill_pages() -> list[list[str]]:
    head = ["# City Care Hospital, Pune (demo)", "Final itemised bill CCH/IP/2026/5521   Date: 22 Aug 2026",
            "Patient: Kamala Sharma   Admission: 18 Aug 2026   Discharge: 22 Aug 2026", ""]
    return [
        head + ["Room rent - Deluxe single - Rs. 7,500 per day x 4 days ........ Rs. 30,000",
                "Nursing charges ................................................. Rs. 8,800"],
        head + ["Doctor visits and consultations ............................. Rs. 26,000",
                "Surgeon and operation theatre charges ...................... Rs. 95,000",
                "Anaesthesia ..................................................... Rs. 18,000"],
        head + ["Pharmacy and medicines .................................... Rs. 32,400",
                "Lab tests and imaging ........................................ Rs. 21,000"],
        head + ["Medical equipment charges ................................... Rs. 7,900",
                "Gloves, PPE kit, admission kit ................................. Rs. 6,900"],
        head + ["## Summary", "Total bill amount ........................................ Rs. 2,46,000"],
        head + ["Payment received in full by the patient's family.", "Authorised signatory: Billing Department"],
    ]


def main() -> None:
    docs = {
        "sample_policy.pdf": build_pdf(policy_pages(), "Family Shield Gold - Policy wording"),
        "settlement_letter.pdf": build_pdf(settlement_pages(), "Settlement letter CLM-2026-0083412"),
        "hospital_bill.pdf": build_pdf(bill_pages(), "Final bill CCH/IP/2026/5521"),
    }
    for folder in OUT_DIRS:
        folder.mkdir(parents=True, exist_ok=True)
        for name, data in docs.items():
            (folder / name).write_bytes(data)
            print(f"wrote {folder / name} ({len(data):,} bytes)")


if __name__ == "__main__":
    main()
