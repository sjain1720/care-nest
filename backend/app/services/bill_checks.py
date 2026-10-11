"""Deterministic checks on an extracted hospital bill. Pure Python – the AI only reads the bill, code does the maths.

Input bill (from Gemini): {"items": [{"description", "category", "amount", "rate", "qty", "page"}], "statedTotal",
"discount", "tax", "pageMarkers": [{"pdfPage", "printedPage", "printedTotal"}], ...}
"""
from app.rules.non_payable import match_non_payable
from app.services.policy_details import format_inr as _rupees

TOLERANCE = 2.0  # rupees; bills round to the nearest rupee

# Charges that vary with the room category. Which of these an insurer cuts is often unclear in the policy,
# so the estimate uses a narrow set (nursing, doctor) and a wide set (+ surgery, anaesthesia, procedures).
ASSOCIATED_NARROW = {"nursing", "doctor"}
ASSOCIATED_WIDE = ASSOCIATED_NARROW | {"surgery", "anaesthesia", "procedure"}
# IRDAI guidance says proportionate deduction should not apply to these (verify against the policy).
NEVER_PROPORTIONATE = {"pharmacy", "consumables", "implants", "investigations"}


def check_pages(markers: list[dict], pdf_pages: int) -> tuple[int | None, list[int], list[dict]]:
    """Uses printed "Page X of N" markers to find pages that were not uploaded."""
    totals = [m["printedTotal"] for m in markers if m.get("printedTotal")]
    if not totals:
        return None, [], []
    expected = max(totals)
    present = {m["printedPage"] for m in markers if m.get("printedPage")}
    missing = [p for p in range(1, expected + 1) if p not in present]
    if not missing and pdf_pages >= expected:
        return expected, [], []
    if not missing:
        missing = list(range(pdf_pages + 1, expected + 1))
    pages = ", ".join(str(p) for p in missing[:10]) + (" …" if len(missing) > 10 else "")
    check = {"kind": "missing_pages", "severity": "high",
             "message": f"The bill says it has {expected} pages, but page(s) {pages} are not in your file. "
                        f"Ask the hospital billing desk for the complete bill – insurers often query incomplete bills."}
    return expected, missing, [check]


def check_arithmetic(items: list[dict]) -> list[dict]:
    checks = []
    for item in items:
        rate, qty, amount = item.get("rate"), item.get("qty"), item.get("amount")
        if rate and qty and amount is not None and abs(rate * qty - amount) > TOLERANCE:
            checks.append({"kind": "line_arithmetic", "severity": "medium", "page": item.get("page"),
                           "message": f"\"{item['description']}\": {qty:g} × {_rupees(rate)} = {_rupees(rate * qty)}, "
                                      f"but the bill shows {_rupees(amount)}."})
    return checks


def check_total(items: list[dict], stated_total: float | None, discount: float | None, tax: float | None) -> list[dict]:
    if not stated_total:
        return []
    computed = sum(i["amount"] for i in items) - (discount or 0) + (tax or 0)
    if abs(computed - stated_total) <= TOLERANCE:
        return []
    return [{"kind": "total_mismatch", "severity": "medium",
             "message": f"The items we read add up to {_rupees(computed)}, but the bill total is {_rupees(stated_total)}. "
                        f"Some lines may be unreadable or missing – check the bill."}]


def check_duplicates(items: list[dict]) -> list[dict]:
    seen, checks = set(), []
    for item in items:
        key = (item["description"].strip().lower(), round(item["amount"], 2), item.get("date"))
        if key in seen and item["amount"] > 0:
            checks.append({"kind": "possible_duplicate", "severity": "info", "page": item.get("page"),
                           "message": f"\"{item['description']}\" ({_rupees(item['amount'])}) appears more than once. It may be correct – check the dates."})
        seen.add(key)
    return checks


def room_rent_analysis(items: list[dict], room_limit: float | None) -> dict | None:
    """Proportionate-deduction estimate when the room costs more per day than the policy limit."""
    rooms = [i for i in items if i.get("category") == "room" and i.get("amount")]
    if not rooms or not room_limit:
        return None
    days = sum(i.get("qty") or 1 for i in rooms)
    room_total = sum(i["amount"] for i in rooms)
    rate = max((i.get("rate") or i["amount"] / (i.get("qty") or 1)) for i in rooms)
    if rate <= room_limit:
        return {"overLimit": False, "ratePerDay": rate, "limitPerDay": room_limit, "days": days}
    share = room_limit / rate
    room_cut = room_total - room_limit * days
    narrow_base = sum(i["amount"] for i in items if i.get("category") in ASSOCIATED_NARROW)
    wide_base = sum(i["amount"] for i in items if i.get("category") in ASSOCIATED_WIDE)
    return {
        "overLimit": True, "ratePerDay": rate, "limitPerDay": room_limit, "days": days,
        "eligibleShare": round(share, 4), "roomCut": round(room_cut),
        "narrowBase": narrow_base, "narrowCut": round(narrow_base * (1 - share)),
        "wideBase": wide_base, "wideCut": round(wide_base * (1 - share)),
    }


def tag_items(items: list[dict], room: dict | None) -> list[dict]:
    over = bool(room and room.get("overLimit"))
    tagged = []
    for n, item in enumerate(items, 1):
        cat, tag, note = item.get("category"), "likely_payable", None
        non_payable = match_non_payable(item["description"])
        if non_payable:
            tag, note = "possibly_non_payable", f"{non_payable} is on IRDAI's list of items insurers usually don't pay"
        elif over and cat == "room":
            tag, note = "needs_clarification", f"Above your {_rupees(room['limitPerDay'])}/day room limit"
        elif over and cat in ASSOCIATED_WIDE:
            tag, note = "needs_clarification", "May be reduced in proportion because the room is above your limit"
        elif cat in ("other", "admin") or not item.get("amount"):
            tag, note = "needs_clarification", "Check with the hospital what this charge is for"
        tagged.append({"id": f"b{n}", **item, "tag": tag, "note": note})
    return tagged


def estimate(items: list[dict], room: dict | None, co_pay_percent: float | None) -> dict:
    """Range of what may not be paid. Guidance only – the insurer's settlement decides."""
    non_payable = sum(i["amount"] for i in items if i["tag"] == "possibly_non_payable")
    over = bool(room and room.get("overLimit"))
    room_cut = room["roomCut"] if over else 0
    narrow = room["narrowCut"] if over else 0
    wide = room["wideCut"] if over else 0
    lines, assumptions = [], ["Based on your policy terms and this bill only. Only the insurer's settlement confirms what is paid."]
    if over:
        lines.append(f"Room rent above your limit: {room['days']:g} days × ({_rupees(room['ratePerDay'])} − {_rupees(room['limitPerDay'])}) = {_rupees(room_cut)}")
        lines.append(f"Doctor and nursing charges reduced to {room['eligibleShare']:.0%}: about {_rupees(narrow)}")
        lines.append(f"If surgery and anaesthesia are also reduced: up to {_rupees(wide)} instead")
        assumptions.append("Policies differ on which charges are reduced when the room is above the limit; the range covers both readings.")
    if non_payable:
        lines.append(f"Items on the non-payable list: {_rupees(non_payable)}")
    if co_pay_percent:
        assumptions.append(f"Your policy has a {co_pay_percent:g}% co-pay for some members; if it applies to this patient, add {co_pay_percent:g}% of the approved amount.")
    return {"low": room_cut + narrow, "likely": room_cut + narrow + non_payable,
            "high": room_cut + wide + non_payable, "lines": lines, "assumptions": assumptions}


def analyse_bill(extraction: dict, pdf_pages: int, room_limit: float | None = None, co_pay_percent: float | None = None) -> dict:
    items = [i for i in extraction.get("items", []) if i.get("amount") is not None]
    expected, missing, page_checks = check_pages(extraction.get("pageMarkers", []), pdf_pages)
    room = room_rent_analysis(items, room_limit)
    tagged = tag_items(items, room)
    checks = (page_checks + check_total(items, extraction.get("statedTotal"), extraction.get("discount"), extraction.get("tax"))
              + check_arithmetic(items) + check_duplicates(items))
    if room is None and any(i.get("category") == "room" for i in items):
        checks.append({"kind": "room_limit_unknown", "severity": "info",
                       "message": "Add your room-rent limit on the My policy page to check the room charges."})
    elif room and room["overLimit"]:
        checks.append({"kind": "room_over_limit", "severity": "medium",
                       "message": f"The room cost {_rupees(room['ratePerDay'])} a day; your policy pays up to {_rupees(room['limitPerDay'])}. "
                                  f"Doctor and nursing charges may also be reduced in proportion."})
    return {
        "hospital": extraction.get("hospital") or "Hospital not found on bill",
        "billNumber": extraction.get("billNumber") or "",
        "billDate": extraction.get("billDate") or "",
        "total": extraction.get("statedTotal") or sum(i["amount"] for i in items),
        "items": tagged,
        "pagesRead": pdf_pages,
        "pagesExpected": expected,
        "missingPages": missing,
        "checks": checks,
        "roomRent": room,
        "estimate": estimate(tagged, room, co_pay_percent),
    }
