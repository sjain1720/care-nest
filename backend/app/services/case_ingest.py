"""Bill / settlement upload: Gemini reads the PDF, code checks it, results are stored on the case."""
import hashlib
from datetime import date
from io import BytesIO

from pypdf import PdfReader

from app.schemas import UploadResult
from app.services import case_store, policy_store
from app.services.bill_checks import analyse_bill
from app.services.deduction_explainer import explain_deductions
from app.services.doc_extract import extract_bill, extract_settlement
from app.services.privacy import mask_all
from app.services.settlement_checks import reconcile


def _active_policy_facts() -> dict | None:
    policy_id = policy_store.get_active_policy_id()
    doc = policy_store.get_policy(policy_id) if policy_id else None
    return doc.get("facts") if doc and doc.get("status") == "ready" else None


def process_case_document(pdf_bytes: bytes, filename: str, doc_type: str) -> UploadResult:
    doc_id = "doc-" + hashlib.sha256(pdf_bytes).hexdigest()[:16]
    pages = len(PdfReader(BytesIO(pdf_bytes)).pages)
    doc_url = f"/api/case/document/{doc_id}"

    # Same file already analysed for this case: reuse the result instead of paying for Gemini again.
    case = case_store.get_case()
    seen = next((d for d in case.get("documents", []) if d["id"] == doc_id), None)
    has_result = {"Hospital bill": "bill", "Settlement letter": "settlement", "Rejection letter": "rejection"}.get(seen["type"]) if seen else None
    if seen and (has_result is None or case.get(has_result)):
        return UploadResult(detectedType=seen["type"], pages=pages, reused=True, message="Already analysed – showing the earlier result.")

    case_store.save_pdf(doc_id, pdf_bytes)
    message = None

    if doc_type == "Hospital bill":
        ext = extract_bill(pdf_bytes).model_dump()
        facts = _active_policy_facts() or {}
        bill = analyse_bill(ext, pages, (facts.get("roomRent") or {}).get("amount"), (facts.get("coPay") or {}).get("amount"))
        bill["docUrl"] = doc_url
        header = {"patientName": ext.get("patientName"), "patientAge": ext.get("patientAge"),
                  "admissionDate": ext.get("admissionDate"), "dischargeDate": ext.get("dischargeDate"),
                  "diagnosis": ext.get("diagnosis"), "claimType": "cashless" if ext.get("payer") else "reimbursement"}
        case_store.update_case(mask_all({"bill": bill, "billHeader": header}))
        issues = [c for c in bill["checks"] if c["severity"] in ("high", "medium")]
        message = f"{len(bill['items'])} charges read. " + (f"{len(issues)} thing(s) to check." if issues else "No problems found in the arithmetic.")

    elif doc_type in ("Settlement letter", "Rejection letter"):
        ext = extract_settlement(pdf_bytes)
        if ext.letterType == "rejection" or doc_type == "Rejection letter":
            rejection = {"reason": ext.rejectionReason or "", "page": ext.rejectionReasonPage or 1, "claimNumber": ext.claimNumber or "",
                         "letterDate": ext.letterDate or "", "docUrl": doc_url}
            case_store.update_case(mask_all({"rejection": rejection}))
            doc_type = "Rejection letter"
            message = "Rejection letter read. You can draft a reconsideration request on the Letter page."
        else:
            deductions = [{"id": f"d{i}", "label": d.label, "amount": d.amount, "insurerReason": d.insurerReason,
                           "page": d.page, "docId": doc_id, "docUrl": doc_url} for i, d in enumerate(ext.deductions, 1)]
            bill = case_store.get_case().get("bill")
            explained = explain_deductions(deductions, bill) if deductions else []
            claimed = ext.claimedAmount or (bill or {}).get("total") or 0
            approved = ext.approvedAmount or 0
            settlement = {"claimNumber": ext.claimNumber or "", "letterDate": ext.letterDate or "", "billedAmount": (bill or {}).get("total") or claimed,
                          "claimedAmount": claimed, "approvedAmount": approved, "deductions": explained,
                          "reconciliation": reconcile(claimed, approved, explained), "letterType": ext.letterType}
            case_store.update_case(mask_all({"settlement": settlement}))
            message = f"{len(explained)} deduction(s) found and explained."

    else:
        message = "Saved to your case. This document type is analysed in the next phase."

    case_store.add_document({"id": doc_id, "name": filename[:80], "type": doc_type, "pages": pages,
                             "uploadedOn": date.today().isoformat(), "docUrl": doc_url})
    return UploadResult(detectedType=doc_type, pages=pages, message=message)
