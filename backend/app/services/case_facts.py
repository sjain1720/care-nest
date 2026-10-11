"""Turns the stored case (bill check, settlement, checklist) into numbered facts with sources, so answers about the
case can cite them and be verified. Pure Python."""
from app.services.policy_details import format_inr

_TAG_LABEL = {"possibly_non_payable": "possibly not payable", "needs_clarification": "needs clarification"}


def _src(doc_id: str, doc_name: str, page: int | None, clause: str, doc_url: str | None) -> dict:
    return {"docId": doc_id, "docName": doc_name, "page": page or 1, "clause": clause, "docUrl": doc_url}


def build_case_facts(case_doc: dict) -> list[dict]:
    """[{"ref": "F1", "text": "...", "source": {docId, docName, page, clause, docUrl}}]"""
    facts: list[tuple[str, dict]] = []
    bill = case_doc.get("bill")
    if bill:
        url = bill.get("docUrl")
        facts.append((f"Hospital bill from {bill['hospital']}: total {format_inr(bill['total'])}, {len(bill['items'])} charges, "
                      f"{bill.get('pagesRead', '?')} page(s) read.", _src("bill", "Hospital bill", 1, "Bill", url)))
        for c in bill.get("checks", []):
            facts.append((f"Bill check: {c['message']}", _src("bill", "Hospital bill", c.get("page"), "Bill check", url)))
        est = bill.get("estimate")
        if est:
            facts.append((f"Estimate of what may not be paid: at least {format_inr(est['low'])}, most likely {format_inr(est['likely'])}, "
                          f"up to {format_inr(est['high'])}.", _src("bill", "Hospital bill", 1, "Estimate", url)))
            facts += [(f"Estimate detail: {line}", _src("bill", "Hospital bill", 1, "Estimate", url)) for line in est.get("lines", [])]
        for i in bill["items"]:
            if i.get("tag") in _TAG_LABEL:
                facts.append((f"Bill page {i.get('page', '?')}: {i['description']} – {format_inr(i['amount'])} – {_TAG_LABEL[i['tag']]}"
                              + (f": {i['note']}" if i.get("note") else ""), _src("bill", "Hospital bill", i.get("page"), "Bill item", url)))

    s = case_doc.get("settlement")
    if s:
        deducted = sum(d["amount"] for d in s.get("deductions", []))
        facts.append((f"Settlement letter: claimed {format_inr(s['claimedAmount'])}, approved {format_inr(s['approvedAmount'])}, "
                      f"deducted {format_inr(deducted)}.", _src("settlement", "Settlement letter", 1, "Summary", None)))
        for d in s.get("deductions", []):
            first = next((c for c in d.get("citations", []) if c.get("docId") != "policy"), None)
            src = _src("settlement", "Settlement letter", (first or {}).get("page"), "Deductions", (first or {}).get("docUrl"))
            facts.append((f"Deduction \"{d['label']}\" of {format_inr(d['amount'])}. Insurer's reason: {d['insurerReason']} "
                          f"Our reading: {d['ourReading']}", src))
            facts += [(f"Calculation for \"{d['label']}\": {line}", src) for line in d.get("calculation", [])]
            for c in d.get("citations", []):
                if c.get("docId") == "policy":
                    facts.append((f"{c['clause']} (policy page {c['page']}): {c['quote']}",
                                  _src("policy", "Policy wording", c["page"], c["clause"], c.get("docUrl"))))

    r = case_doc.get("rejection")
    if r:
        facts.append((f"Rejection letter: the insurer rejected the claim. Reason given: {r.get('reason') or 'none stated'}",
                      _src("rejection", "Rejection letter", r.get("page"), "Rejection", r.get("docUrl"))))

    for item in case_doc.get("checklist", []):
        if item["status"] != "collected":
            facts.append((f"Still needed: {item['name']} – get it from {item['source']}. Why: {item['why']}",
                          _src("case", "Your checklist", 1, "Checklist", None)))

    return [{"ref": f"F{n}", "text": text, "source": src} for n, (text, src) in enumerate(facts, 1)]
