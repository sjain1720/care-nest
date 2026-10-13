"""Reads the insurer's reply to the family's letter (pasted text or PDF) and records it in the claim diary."""
import re
from datetime import date
from typing import Literal

from google.genai import types
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.gcp import gemini
from app.services import case_store
from app.services.claim_tracker import new_event_id
from app.services.grounding import quote_in_text
from app.services.plain_language import STYLE
from app.services.privacy import mask_all


class ReplyOut(BaseModel):
    outcome: Literal["paid_more", "explained", "no_change", "asks_for_papers", "rejected", "unclear"]
    summary: str
    newApprovedAmount: float | None = None
    papersAsked: list[str] = []
    referenceNumber: str | None = None
    replyDate: str | None = None
    quote: str = ""


PROMPT = """An Indian family wrote to their health insurer about a hospital claim. This is the insurer's reply.
Fill the JSON:
- outcome: paid_more (agrees to pay more money), explained (explains the cuts but pays nothing more),
  no_change (keeps its decision with little or no explanation), asks_for_papers (wants documents before deciding),
  rejected (refuses the claim, or keeps a refusal), unclear (none of these).
- summary: at most 60 words. What the reply says and what it means for the family. Never say the insurer is right or wrong.
- newApprovedAmount: the new total the insurer will pay, only if the reply states it. Plain number in rupees.
- papersAsked: each document the insurer asks for, in plain words.
- referenceNumber: the complaint or claim reference printed in the reply, if any.
- replyDate: the date of the reply as YYYY-MM-DD, only if printed.
- quote: the single most important sentence, copied WORD FOR WORD (8-40 words).
Never invent numbers. Do not copy addresses, phone numbers or ID numbers.""" + STYLE


def _read(contents: list) -> ReplyOut:
    response = gemini().models.generate_content(
        model=get_settings().gemini_model, contents=contents,
        config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=ReplyOut, temperature=0),
    )
    return response.parsed if isinstance(response.parsed, ReplyOut) else ReplyOut.model_validate_json(response.text)


def _record(out: ReplyOut, source: str, doc_url: str | None = None) -> dict:
    when = out.replyDate if out.replyDate and re.fullmatch(r"\d{4}-\d{2}-\d{2}", out.replyDate) else date.today().isoformat()
    event = mask_all({
        "id": new_event_id(), "kind": "reply", "date": when, "outcome": out.outcome,
        "summary": out.summary, "newApprovedAmount": out.newApprovedAmount, "papersAsked": out.papersAsked,
        "reference": out.referenceNumber, "quote": out.quote, "source": source, "docUrl": doc_url,
    })
    case_store.add_timeline_event({k: v for k, v in event.items() if v not in (None, "", [])})
    return event


def read_reply_text(text: str) -> dict:
    out = _read([PROMPT, f"REPLY\n{text}"])
    if out.quote and not quote_in_text(out.quote, text):
        out.quote = ""
    return _record(out, "pasted")


def read_reply_document(data: bytes, doc_url: str, mime: str = "application/pdf") -> dict:
    out = _read([types.Part.from_bytes(data=data, mime_type=mime), PROMPT])
    return _record(out, "pdf", doc_url)
