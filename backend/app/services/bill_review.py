"""The family checks what was read from their bill before anything is worked out from it. Pure Python."""

HEADER_FIELDS = ("hospital", "billNumber", "billDate", "patientName", "admissionDate", "dischargeDate")
ITEM_FIELDS = ("description", "category", "amount", "rate", "qty", "page", "date")


def apply_review(extraction: dict, review: dict) -> dict:
    """The original reading with the family's checked values: header fields, grand total and every charge line."""
    out = {**extraction}
    for key in HEADER_FIELDS:
        if key in review:
            out[key] = review[key] or None
    if "statedTotal" in review:
        out["statedTotal"] = review["statedTotal"]
    if "items" in review:
        out["items"] = [{**{k: item.get(k) for k in ITEM_FIELDS}, "description": item["description"].strip(), "page": item.get("page") or 1}
                        for item in review["items"] if item["description"].strip()]
    return out


def extraction_from_bill(bill: dict, header: dict) -> dict:
    """For bills saved before the original reading was kept: rebuild it, including the printed page numbers that were found."""
    expected, missing = bill.get("pagesExpected"), set(bill.get("missingPages") or [])
    markers = [{"pdfPage": p, "printedPage": p, "printedTotal": expected} for p in range(1, expected + 1) if p not in missing] if expected else []
    return {
        "hospital": bill.get("hospital"), "billNumber": bill.get("billNumber"), "billDate": bill.get("billDate"),
        "statedTotal": bill.get("total"), "pageMarkers": markers,
        "items": [{k: item.get(k) for k in ITEM_FIELDS} for item in bill.get("items", [])],
        **{k: header.get(k) for k in ("patientName", "admissionDate", "dischargeDate")},
    }
