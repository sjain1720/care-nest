"""Builds the ClaimCase the frontend shows (documents, checklist, escalation) from what has been uploaded. Pure Python."""
from app.services.policy_details import format_inr as _rupees

# (id, name, where to get it, why, document type that satisfies it automatically)
REIMBURSEMENT_DOCS = [
    ("c1", "Claim form – Part A (signed by you)", "Insurer website or TPA desk", "Needed for every reimbursement claim", None),
    ("c2", "Claim form – Part B (filled by hospital)", "Hospital insurance / TPA desk", "The hospital confirms the treatment details", None),
    ("c3", "Discharge summary", "Ward or billing desk at discharge", "Shows the diagnosis and treatment given", "Discharge summary"),
    ("c4", "Final itemised bill", "Hospital billing desk", "Every charge must be listed separately", "Hospital bill"),
    ("c5", "Payment receipts", "Hospital billing desk – ask for a receipt for each payment", "Proves what you actually paid", None),
    ("c6", "Investigation reports (blood tests, scans)", "Hospital lab and radiology department", "Supports the diagnosis", None),
    ("c7", "Prescriptions and pharmacy bills", "Hospital pharmacy", "Needed to pay for medicines", None),
    ("c8", "Cancelled cheque or bank details", "Your bank", "So the insurer can pay you", None),
    ("c9", "Photo ID and address proof (KYC)", "Policyholder's PAN / Aadhaar", "Insurer's KYC requirement", None),
]

ESCALATION = [
    {"level": 1, "name": "Insurer's grievance cell", "when": "First step. Write to the insurer with your questions and evidence.",
     "howTo": "Use the grievance email or form on the insurer's website. Note the reference number.", "verify": True},
    {"level": 2, "name": "Bima Bharosa (IRDAI)", "when": "If the insurer does not reply in time, or you disagree with the reply.",
     "howTo": "Register the complaint online on the IRDAI Bima Bharosa portal.", "link": "https://bimabharosa.irdai.gov.in", "verify": True},
    {"level": 3, "name": "Insurance Ombudsman", "when": "If it is still unresolved. There is a time limit after the insurer's final reply – check it before filing.",
     "howTo": "File with the Ombudsman office for your area.", "link": "https://www.cioins.co.in", "verify": True},
]


def build_checklist(doc_types: set[str], bill: dict | None, settlement: dict | None, overrides: dict | None = None,
                    rejected: bool = False) -> list[dict]:
    items = [{"id": i, "group": "claim", "name": n, "source": s, "why": w, "status": "collected" if t and t in doc_types else "missing"}
             for i, n, s, w, t in REIMBURSEMENT_DOCS]
    if bill and bill.get("missingPages"):
        pages = ", ".join(str(p) for p in bill["missingPages"][:10])
        items.insert(4, {"id": "c4b", "group": "claim", "name": f"Missing bill page(s): {pages}",
                         "source": "Hospital billing desk", "why": f"The bill says it has {bill['pagesExpected']} pages; incomplete bills get queried",
                         "status": "missing"})
    for d in (settlement or {}).get("deductions", []):
        if d.get("trust") == "unknown":
            items.append({"id": f"x-{d['id']}", "group": "dispute", "name": f"Itemised explanation of the {_rupees(d['amount'])}",
                          "source": "Insurer – request it with the letter", "why": "The settlement letter gives no reason for this amount", "status": "missing"})
    room = (bill or {}).get("roomRent") or {}
    if settlement and room.get("overLimit"):
        items.append({"id": "x-room", "group": "dispute", "name": "Hospital note on room availability", "source": "Hospital admission desk",
                      "why": "Shows whether a room within your limit was available – helps challenge a room-rent cut", "status": "missing"})
    if rejected:
        items.append({"id": "x-reject", "group": "dispute", "name": "Treating doctor's letter explaining the treatment", "source": "Your treating doctor",
                      "why": "A clear medical explanation often answers the reason given for a rejection", "status": "missing"})
    # Statuses the user ticked in the app win over the automatic ones.
    for item in items:
        if overrides and item["id"] in overrides:
            item["status"] = overrides[item["id"]]
    return items


def build_case(case_doc: dict) -> dict:
    bill, settlement, rejection = case_doc.get("bill"), case_doc.get("settlement"), case_doc.get("rejection")
    documents = case_doc.get("documents", [])
    header = case_doc.get("billHeader") or {}
    if rejection:
        stage = "Claim rejected – you can ask for reconsideration"
    elif settlement:
        deducted = sum(d["amount"] for d in settlement["deductions"])
        stage = f"Settled with {_rupees(deducted)} deducted" if deducted else "Settled in full"
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
    }
