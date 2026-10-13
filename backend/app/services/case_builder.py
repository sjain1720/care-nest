"""Builds the ClaimCase the frontend shows (documents, checklist, escalation) from what has been uploaded. Pure Python."""
from datetime import date

from app.services.claim_tracker import sorted_timeline, stage_from_timeline
from app.services.policy_details import format_inr as _rupees

# (id, name, where to get it, why, document type that satisfies it automatically)
REIMBURSEMENT_DOCS = [
    ("c1", "Claim form, part A (you sign it)", "Insurer's website or the hospital's insurance desk", "Needed for every claim where you paid first", None),
    ("c2", "Claim form, part B (the hospital fills it)", "Hospital insurance desk", "The hospital confirms what treatment was given", None),
    ("c3", "Discharge summary", "Ward or billing desk when you leave", "Shows the illness and the treatment given", "Discharge summary"),
    ("c4", "Final hospital bill, with every charge listed", "Hospital billing desk", "Every charge must be shown separately", "Hospital bill"),
    ("c5", "Payment receipts", "Hospital billing desk – ask for a receipt for each payment", "Proves what you actually paid", None),
    ("c6", "Test reports (blood tests, scans)", "Hospital lab and scan department", "Supports what the doctor found", None),
    ("c7", "Prescriptions and medicine bills", "Hospital pharmacy", "Needed to pay for medicines", None),
    ("c8", "Cancelled cheque or bank details", "Your bank", "So the insurer can pay you", None),
    ("c9", "Photo ID and address proof", "PAN or Aadhaar of the person who holds the policy", "The insurer must check who you are", None),
]

ESCALATION = [
    {"level": 1, "name": "The insurer's complaints team", "when": "First step. Write to the insurer with your questions and papers.",
     "howTo": "Use the complaint email or form on the insurer's website. Note the reference number.", "verify": True},
    {"level": 2, "name": "Bima Bharosa (the insurance regulator's complaint site)", "when": "If the insurer doesn't reply in time, or you disagree with the reply.",
     "howTo": "Register the complaint online on the Bima Bharosa website.", "link": "https://bimabharosa.irdai.gov.in", "verify": True},
    {"level": 3, "name": "Insurance Ombudsman (free, independent judge)", "when": "If it is still not solved. There is a time limit after the insurer's final reply – check it first.",
     "howTo": "File with the Ombudsman office for your area.", "link": "https://www.cioins.co.in", "verify": True},
]


def build_checklist(doc_types: set[str], bill: dict | None, settlement: dict | None, overrides: dict | None = None,
                    rejected: bool = False) -> list[dict]:
    items = [{"id": i, "group": "claim", "name": n, "source": s, "why": w, "status": "collected" if t and t in doc_types else "missing"}
             for i, n, s, w, t in REIMBURSEMENT_DOCS]
    if bill and bill.get("missingPages"):
        pages = ", ".join(str(p) for p in bill["missingPages"][:10])
        items.insert(4, {"id": "c4b", "group": "claim", "name": f"Missing bill page(s): {pages}",
                         "source": "Hospital billing desk", "why": f"The bill says it has {bill['pagesExpected']} pages. The insurer asks questions if pages are missing",
                         "status": "missing"})
    for d in (settlement or {}).get("deductions", []):
        if d.get("trust") == "unknown":
            items.append({"id": f"x-{d['id']}", "group": "dispute", "name": f"A list of what the {_rupees(d['amount'])} cut is for",
                          "source": "The insurer – ask for it in your letter", "why": "The insurer's letter gives no reason for this amount", "status": "missing"})
    room = (bill or {}).get("roomRent") or {}
    if settlement and room.get("overLimit"):
        items.append({"id": "x-room", "group": "dispute", "name": "Hospital note saying no cheaper room was free", "source": "Hospital admission desk",
                      "why": "If no room within your limit was free, the insurer may pay more", "status": "missing"})
    if rejected:
        items.append({"id": "x-reject", "group": "dispute", "name": "Letter from your doctor explaining the treatment", "source": "Your treating doctor",
                      "why": "A clear medical reason often answers why the claim was refused", "status": "missing"})
    # Statuses the user ticked in the app win over the automatic ones.
    for item in items:
        if overrides and item["id"] in overrides:
            item["status"] = overrides[item["id"]]
    return items


def build_case(case_doc: dict, today: date | None = None) -> dict:
    bill, settlement, rejection = case_doc.get("bill"), case_doc.get("settlement"), case_doc.get("rejection")
    documents = case_doc.get("documents", [])
    header = case_doc.get("billHeader") or {}
    timeline = sorted_timeline(case_doc.get("timeline"))
    diary_stage = stage_from_timeline(timeline, bool(settlement or rejection), today or date.today())
    if diary_stage:
        stage = diary_stage
    elif rejection:
        stage = "Claim refused – you can ask them to look again"
    elif settlement:
        deducted = sum(d["amount"] for d in settlement["deductions"])
        stage = f"Paid, with {_rupees(deducted)} cut" if deducted else "Paid in full"
    elif bill:
        stage = "Bill checked – waiting for the insurer's decision"
    else:
        stage = "Add your hospital bill to start"
    return {
        "id": case_doc.get("id", "current"),
        "title": header.get("title") or "Your hospital claim",
        "patient": {"name": header.get("patientName") or "Patient", "relation": header.get("relation") or "", "age": header.get("patientAge")},
        "hospital": (bill or {}).get("hospital") or "Hospital not added yet",
        "admissionDate": header.get("admissionDate") or "",
        "dischargeDate": header.get("dischargeDate") or "",
        "diagnosis": header.get("diagnosis") or "Not read yet – add the discharge summary",
        "claimType": header.get("claimType") or "reimbursement",
        "claimNumber": (settlement or rejection or {}).get("claimNumber") or "",
        "stage": stage,
        "documents": documents,
        "checklist": build_checklist({d["type"] for d in documents}, bill, settlement,
                                     case_doc.get("checklistStatus"), rejected=bool(rejection)),
        "escalation": ESCALATION,
        "timeline": timeline,
        "rejection": {k: rejection.get(k) for k in ("reason", "page", "letterDate", "docUrl")} if rejection else None,
    }
