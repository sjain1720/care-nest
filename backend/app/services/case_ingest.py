"""Bill / settlement upload: Gemini reads the PDF or photo, code checks it, results are stored on the case."""
import hashlib
from datetime import date
from io import BytesIO

from pypdf import PdfReader

from app.schemas import UploadResult
from app.services import case_store, policy_store
from app.services.bill_checks import analyse_bill
from app.services.claim_history import has_content
from app.services.bill_review import apply_review, extraction_from_bill
from app.services.deduction_explainer import explain_deductions
from app.services.doc_extract import extract_bill, extract_settlement
from app.services.file_types import PDF, is_image, UnreadableDocumentError
from app.services.ocr import ocr_first_page
from app.services.privacy import mask_all
from app.services.insurer_response import record_response, RESPONSE_VERSION
from app.services.settlement_checks import reconcile


def _active_policy_facts() -> dict | None:
    active = policy_store.get_active_policy()
    return active[1]["facts"] if active else None


def _limits() -> tuple[float | None, float | None]:
    facts = _active_policy_facts() or {}
    return (facts.get("roomRent") or {}).get("amount"), (facts.get("coPay") or {}).get("amount")


def process_case_document(data: bytes, filename: str, doc_type: str, mime: str = PDF, source_text: str | None = None) -> UploadResult:
    photo = is_image(mime)
    doc_id = ("img-" if photo else "doc-") + hashlib.sha256(data).hexdigest()[:16]
    pages = 1 if photo else len(PdfReader(BytesIO(data)).pages)
    doc_url = f"/api/case/document/{doc_id}"

    # Same file already analysed for this case: reuse the result instead of paying for Gemini again.
    case = case_store.get_case()
    seen = next((d for d in case.get("documents", []) if d["id"] == doc_id), None)
    has_result = {"Hospital bill": "bill", "Settlement letter": "settlement", "Rejection letter": "rejection"}.get(seen["type"]) if seen else None
    financial_photo = photo and doc_type in ('Hospital bill', 'Settlement letter', 'Rejection letter', 'Insurer reply')
    needs_readability = financial_photo and not (seen or {}).get('ocrReadable')
    if needs_readability:
        text = source_text if source_text is not None else ocr_first_page(data, mime)
        if not text.strip():
            raise UnreadableDocumentError('No readable text was found in this image. Upload a clearer, complete photo or PDF; no bill or decision was extracted.')
    insurer_upload = doc_type in ('Settlement letter','Rejection letter','Insurer reply')
    if seen and not needs_readability and (not insurer_upload or seen.get('responseVersion') == RESPONSE_VERSION) and (has_result is None or case.get(has_result)):
        return UploadResult(detectedType=seen["type"], pages=pages, reused=True, message="Already analysed – showing the earlier result.")

    bill_extraction = extract_bill(data, mime).model_dump() if doc_type == 'Hospital bill' else None
    if bill_extraction is not None and not bill_extraction.get('items'):
        raise UnreadableDocumentError('No readable bill charge rows were found. Upload a clearer, complete hospital bill.')

    active_policy_id = policy_store.get_active_policy_id()
    if not has_content(case) and not case.get("policyId") and active_policy_id:
        case_store.update_case({"policyId": active_policy_id})
    case_store.save_file(doc_id, data, mime)
    message = None

    if doc_type == "Hospital bill":
        ext = bill_extraction
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

    elif insurer_upload:
        ext = extract_settlement(data, mime)
        response = record_response(ext, doc_url, 'pdf', doc_id)
        doc_type = response['detectedType']
        message = response['summary']

    else:
        message = "Saved to your claim. It now counts in your list of papers."

    case_store.add_document({"id": doc_id, "name": filename[:80], "type": doc_type, "pages": pages,
                             "uploadedOn": date.today().isoformat(), "docUrl": doc_url, "ocrReadable": financial_photo, "responseVersion": RESPONSE_VERSION if insurer_upload else None})
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
