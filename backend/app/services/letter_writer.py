"""Drafts letters to the insurer: facts from code, wording from Gemini, amounts checked in code (template fallback)."""
from google.genai import types
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.gcp import gemini
from app.services import case_store, policy_store
from app.services.case_builder import build_case
from app.services.letters import letter_facts, template_body, unknown_amounts

PROMPT = """Write a short, polite, factual letter from an Indian family to their health insurer. Kind: {kind}.
Use ONLY the facts given. Keep every header line exactly as given. Keep placeholders in [square brackets] as they are.
Simple English, at most 300 words, numbered points for the requests. No threats, no legal jargon, no claims that the
insurer is wrong, no promises. Start with "Dear Sir/Madam," and end with "Yours faithfully," followed by the signature."""


class LetterBody(BaseModel):
    body: str


def draft_letter(kind: str) -> dict:
    case_doc = case_store.get_case()
    case = {**build_case(case_doc), "settlement": case_doc.get("settlement"), "bill": case_doc.get("bill"),
            "rejection": case_doc.get("rejection")}
    active = policy_store.get_active_policy()
    facts = letter_facts(kind, case, active[1]["facts"] if active else None)

    warnings = []
    if kind == "clarification" and not case_doc.get("settlement"):
        warnings.append("Upload the settlement letter so the deductions can be listed.")
    if kind == "reconsideration" and not case_doc.get("rejection"):
        warnings.append("Upload the rejection letter so its reason can be quoted.")
    if (case_doc.get("bill") or {}).get("reviewed") is False:
        warnings.append("Check the details we read from your bill (on the bill page) before you send this letter.")

    fact_text = "\n".join(["HEADER:", *facts["header"], "POINTS:", *facts["points"], "SIGNATURE:", facts["signature"]])
    response = gemini().models.generate_content(
        model=get_settings().gemini_model,
        contents=[PROMPT.format(kind=kind.replace("_", " ")), fact_text],
        config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=LetterBody, temperature=0.3),
    )
    body = (response.parsed.body if isinstance(response.parsed, LetterBody) else LetterBody.model_validate_json(response.text).body).strip()

    invented = unknown_amounts(body, set(facts["allowedAmounts"]))
    if invented or not all(line in body for line in facts["header"]):
        body = template_body(facts)
        warnings.append("We used our standard wording because the draft changed a number or a reference we couldn't verify.")

    return {"kind": kind, "to": facts["to"], "subject": facts["subject"], "body": body,
            "evidenceIndex": facts["evidenceIndex"], "warnings": warnings}
