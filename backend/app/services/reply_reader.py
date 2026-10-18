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
    communicationType: Literal["settlement", "rejection", "query", "other"] = "other"
    claimedAmount: float | None = None
    outcome: Literal["paid_more", "explained", "no_change", "asks_for_papers", "rejected", "unclear"]
    summary: str
    newApprovedAmount: float | None = None
    papersAsked: list[str] = []
    referenceNumber: str | None = None
    replyDate: str | None = None
    quote: str = ""


PROMPT = """This is an insurer communication about a hospital claim, either the first response or a later follow-up.
Fill the JSON:
- communicationType: query for a request before deciding, settlement for an explicit final approval, rejection for a refusal, otherwise other. A document request does not imply approved=0.
- claimedAmount: only the explicit total claimed, otherwise null.
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
    from app.services.doc_extract import SettlementOut
    from app.services.insurer_response import record_response
    kind = 'query' if out.outcome == 'asks_for_papers' else 'rejection' if out.outcome == 'rejected' else out.communicationType
    if kind == 'other' and out.outcome == 'paid_more' and out.newApprovedAmount is not None:
        kind = 'settlement'
    ext = SettlementOut(letterType=kind, claimedAmount=out.claimedAmount,
        approvedAmount=out.newApprovedAmount, summary=out.summary, papersAsked=out.papersAsked,
        referenceNumber=out.referenceNumber, letterDate=out.replyDate, replyOutcome=out.outcome)
    return record_response(ext, doc_url, source, quote=out.quote)


def read_reply_text(text: str) -> dict:
    out = _read([PROMPT, f"REPLY\n{text}"])
    if out.quote and not quote_in_text(out.quote, text):
        out.quote = ""
    return _record(out, "pasted")


def read_reply_document(data: bytes, doc_url: str, mime: str = "application/pdf") -> dict:
    from app.services.doc_extract import extract_settlement
    from app.services.insurer_response import record_response
    return record_response(extract_settlement(data, mime), doc_url, 'pdf')
