"""Letter facts, evidence index, a code-only template body, and the amount check used on AI-written letters. Pure Python."""
import re

from app.services.policy_details import format_inr

LETTER_KINDS = ("clarification", "reconsideration", "grievance", "cover_letter")
_AMOUNT = re.compile(r"(?:₹|rs\.?|inr)\s?([\d,]+(?:\.\d{1,2})?)", re.IGNORECASE)


def amounts_in(text: str) -> set[int]:
    return {int(float(m.replace(",", ""))) for m in _AMOUNT.findall(text) if m.replace(",", "").replace(".", "").isdigit()}


def unknown_amounts(body: str, allowed: set[int]) -> list[int]:
    """Rupee amounts in the letter that don't come from the case – a sign the AI invented a number."""
    return sorted(a for a in amounts_in(body) if a not in allowed)


def letter_facts(kind: str, case: dict, policy: dict | None) -> dict:
    """Everything the letter may state, worked out in code. case = build_case() output plus raw bill/settlement/rejection."""
    policy = policy or {}
    s, bill, rejection = case.get("settlement") or {}, case.get("bill") or {}, case.get("rejection") or {}
    insurer = policy.get("insurer") or "the insurer"
    patient = case["patient"]["name"]
    ref = case.get("claimNumber") or "[claim number]"
    header = [f"Policy number: {policy.get('policyNumber') or '[policy number]'}", f"Claim number: {ref}", f"Patient: {patient}",
              f"Hospital: {case['hospital']}" + (f" (admitted {case['admissionDate']}, discharged {case['dischargeDate']})" if case.get("admissionDate") else "")]
    points: list[str] = []
    allowed: set[int] = set()

    if kind == "clarification":
        subject = f"Request for explanation of deductions – Claim {ref}"
        deductions = s.get("deductions", [])
        total = sum(d["amount"] for d in deductions)
        allowed |= {int(s.get("claimedAmount", 0)), int(s.get("approvedAmount", 0)), int(total)}
        points.append(f"Of the claimed amount of {format_inr(s.get('claimedAmount', 0))}, {format_inr(s.get('approvedAmount', 0))} was approved and {format_inr(total)} was deducted.")
        for d in sorted(deductions, key=lambda d: d.get("trust") != "unknown"):
            allowed.add(int(d["amount"]))
            if d.get("trust") == "unknown":
                points.append(f"{d['label']} – {format_inr(d['amount'])}: no reason or policy clause is given. Please share the bill items included and the clause relied on.")
            else:
                clause = next((c["clause"] for c in d.get("citations", []) if c.get("docId") == "policy"), None)
                points.append(f"{d['label']} – {format_inr(d['amount'])}: please confirm the calculation" + (f" and how {clause} was applied." if clause else " and the policy clause relied on."))
    elif kind == "reconsideration":
        subject = f"Request for reconsideration of claim rejection – Claim {ref}"
        points.append(f"The claim was rejected for this reason: {rejection.get('reason') or '[reason in the rejection letter]'}.")
        points.append("I request you to reconsider the claim based on the policy terms and the attached documents.")
        points += [f"Enclosed / to follow: {i['name']}" for i in case.get("checklist", []) if i["group"] == "claim" and i["status"] == "collected"]
    elif kind == "grievance":
        subject = f"Grievance regarding Claim {ref}"
        timeline = case.get("timeline") or []
        sent = next((e for e in reversed(timeline) if e.get("kind") == "letter_sent"), None)
        reply = next((e for e in reversed(timeline) if e.get("kind") == "reply"), None)
        earlier = (f"on {sent['date']}" + (f" (reference {sent['reference']})" if sent.get("reference") else "")) if sent else "on [date of your earlier letter]"
        if reply:
            points.append(f"I wrote to you {earlier} about this claim. Your reply dated {reply['date']} does not resolve my concerns.")
        elif sent:
            points.append(f"I wrote to you {earlier} about this claim and have not received a reply.")
        else:
            points.append("I wrote to you on [date of your earlier letter] about this claim and have not received a satisfactory reply.")
        if s:
            unexplained = [d for d in s.get("deductions", []) if d.get("trust") == "unknown"]
            for d in unexplained:
                allowed.add(int(d["amount"]))
                points.append(f"The deduction \"{d['label']}\" of {format_inr(d['amount'])} is still unexplained.")
        if rejection:
            points.append(f"The claim was rejected for this reason: {rejection.get('reason') or '[reason]'}.")
        points.append("Please resolve this under your grievance redressal procedure and share the reference number.")
    else:  # cover_letter
        subject = f"Submission of reimbursement claim – {patient}"
        claimed = int(bill.get("total") or 0)
        if claimed:
            allowed.add(claimed)
            points.append(f"I am submitting a reimbursement claim for {format_inr(claimed)} for the hospitalisation below.")
        points += [f"Enclosed: {i['name']}" for i in case.get("checklist", []) if i["group"] == "claim" and i["status"] == "collected"]
        missing = [i["name"] for i in case.get("checklist", []) if i["group"] == "claim" and i["status"] != "collected"]
        if missing:
            points.append("To follow: " + "; ".join(missing))

    evidence = []
    for d in s.get("deductions", []):
        for c in d.get("citations", []):
            if c.get("docId") == "policy":
                entry = f"Policy wording – {c['clause']} (page {c['page']})"
                if entry not in evidence:
                    evidence.append(entry)
    evidence += [f"{doc['type']}: {doc['name']}" for doc in case.get("documents", [])]
    evidence += [f"{i['name']} (to be obtained)" for i in case.get("checklist", []) if i["group"] == "dispute" and i["status"] != "collected"]

    return {"kind": kind, "to": f"Grievance Officer, {insurer}" if kind in ("clarification", "reconsideration", "grievance") else f"Claims Department, {insurer}",
            "subject": subject, "header": header, "points": points, "evidenceIndex": evidence, "allowedAmounts": sorted(allowed),
            "signature": f"[Your name] (on behalf of {patient})\nPhone: [your phone number]\nEmail: [your email]"}


def template_body(facts: dict) -> str:
    numbered = "\n\n".join(f"{n}. {p}" for n, p in enumerate(facts["points"], 1))
    return ("Dear Sir/Madam,\n\n" + "\n".join(facts["header"]) + "\n\n" + numbered +
            "\n\nThe documents listed in the evidence index are attached. Please reply with the requested details.\n\n"
            "Yours faithfully,\n" + facts["signature"])
