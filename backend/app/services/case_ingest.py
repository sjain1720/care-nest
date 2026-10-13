"""Bill / settlement upload: Gemini reads the PDF or photo, code checks it, results are stored on the case."""
import hashlib
from datetime import date
from io import BytesIO

from pypdf import PdfReader

from app.schemas import UploadResult
from app.services import case_store, policy_store
from app.services.bill_checks import analyse_bill
from app.services.bill_review import apply_review, extraction_from_bill
from app.services.deduction_explainer import explain_deductions
from app.services.doc_extract import extract_bill, extract_settlement
from app.services.file_types import PDF, is_image
from app.services.privacy import mask_all
from app.services.reply_reader import read_reply_document
from app.services.settlement_checks import reconcile


def _active_policy_facts() -> dict | None:
    active = policy_store.get_active_policy()
    return active[1]["facts"] if active else None


def _limits() -> tuple[float | None, float | None]:
    facts = _active_policy_facts() or {}
    return (facts.get("roomRent") or {}).get("amount"), (facts.get("coPay") or {}).get("amount")


def process_case_document(data: bytes, filename: str, doc_type: str, mime: str = PDF) -> UploadResult:
    photo = is_image(mime)
    doc_id = ("img-" if photo else "doc-") + hashlib.sha256(data).hexdigest()[:16]
    pages = 1 if photo else len(PdfReader(BytesIO(data)).pages)
    doc_url = f"/api/case/document/{doc_id}"

    # Same file already analysed for this case: reuse the result instead of paying for Gemini again.
    case = case_store.get_case()
    seen = next((d for d in case.get("documents", []) if d["id"] == doc_id), None)
    has_result = {"Hospital bill": "bill", "Settlement letter": "settlement", "Rejection letter": "rejection"}.get(seen["type"]) if seen else None
    if seen and (has_result is None or case.get(has_result)):
        return UploadResult(detectedType=seen["type"], pages=pages, reused=True, message="Already analysed – showing the earlier result.")

    case_store.save_file(doc_id, data, mime)
    message = None

    if doc_type == "Hospital bill":
        ext = extract_bill(data, mime).model_dump()
        bill = analyse_bill(ext, pages, *_limits())
        # Nothing is final until the family has checked what was read (PUT /api/case/bill).
        bill.update(docUrl=doc_url, reviewed=False, unreadableLines=ext.get("unreadableLines") or 0)
        header = {"patientName": ext.get("patientName"), "patientAge": ext.get("patientAge"),
                  "admissionDate": ext.get("admissionDate"), "dischargeDate": ext.get("dischargeDate"),
                  "diagnosis": ext.get("diagnosis"), "claimType": "cashless" if ext.get("payer") else "reimbursement"}
        case_store.update_case(mask_all({"bill": bill, "billHeader": header, "billExtraction": ext}))
        issues = [c for c in bill["checks"] if c["severity"] in ("high", "medium")]
        message = (f"{len(bill['items'])} charges read. " + (f"{len(issues)} thing(s) to check. " if issues else "")
                   + "Check what we read on the bill page before you rely on it.")

    elif doc_type in ("Settlement letter", "Rejection letter"):
        ext = extract_settlement(data, mime)
        if ext.letterType == "rejection" or doc_type == "Rejection letter":
            rejection = {"reason": ext.rejectionReason or "", "page": ext.rejectionReasonPage or 1, "claimNumber": ext.claimNumber or "",
                         "letterDate": ext.letterDate or "", "docUrl": doc_url}
            case_store.update_case(mask_all({"rejection": rejection}))
            doc_type = "Rejection letter"
            message = "Rejection letter read. See the reason, then ask them to look again from the Letter page."
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

    elif doc_type == "Insurer reply":
        message = read_reply_document(data, doc_url, mime)["summary"]

    else:
        message = "Saved to your claim. It now counts in your list of papers."

    case_store.add_document({"id": doc_id, "name": filename[:80], "type": doc_type, "pages": pages,
                             "uploadedOn": date.today().isoformat(), "docUrl": doc_url})
    return UploadResult(detectedType=doc_type, pages=pages, message=message)


def apply_bill_review(review: dict) -> dict:
    """Re-runs every bill check on the details the family checked or corrected. Code only – Gemini is not called again."""
    case = case_store.get_case()
    bill = case.get("bill")
    if not bill:
        raise LookupError("No hospital bill has been uploaded yet.")
    header = case.get("billHeader") or {}
    extraction = apply_review(case.get("billExtraction") or extraction_from_bill(bill, header), review)
    checked = analyse_bill(extraction, bill.get("pagesRead") or 1, *_limits())
    checked.update(docUrl=bill.get("docUrl"), reviewed=True, unreadableLines=extraction.get("unreadableLines") or 0)
    header = {**header, **{k: extraction.get(k) for k in ("patientName", "admissionDate", "dischargeDate")}}
    case_store.update_case(mask_all({"bill": checked, "billHeader": header, "billExtraction": extraction}))
    return checked
