"""Answers questions about the user's case (bill check, settlement, checklist) from numbered facts, verifying every quote."""
from typing import Literal

from google.genai import types
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.gcp import gemini
from app.schemas import AnswerCard, AskResponse, Citation, NextAction
from app.services import case_store
from app.services.case_builder import build_case
from app.services.case_facts import build_case_facts
from app.services.grounding import quote_in_text
from app.services.steps import StepLog

_NEXT = {
    "bill": NextAction(label="See the bill check", route="/case/bill"),
    "settlement": NextAction(label="See every deduction explained", route="/case/settlement"),
    "case": NextAction(label="Open your document checklist", route="/case"),
    "letter": NextAction(label="Draft a letter to the insurer", route="/case/letter"),
    "upload": NextAction(label="Upload the document", route="/upload"),
}
_AGENT = {"bill": "Bill & Settlement Analyst", "settlement": "Bill & Settlement Analyst", "documents": "Claim Assistant"}
_NEEDS = {"bill": ("bill", "your hospital bill"), "settlement": ("settlement", "the insurer's settlement letter")}


class CiteRef(BaseModel):
    ref: str
    quote: str


class CaseAnswerOut(BaseModel):
    verdict: Literal["covered", "partial", "not_covered", "needs_checking", "cant_confirm", "info"]
    headline: str
    summary: str
    citations: list[CiteRef]
    toConfirm: list[str]
    nextAction: Literal["none", "bill", "settlement", "case", "letter"] = "none"


PROMPT = """You are the {agent} in CareNest, helping an Indian family with THEIR OWN hospital claim.
Answer the question using ONLY the numbered facts [F1]..[Fn] below. They come from the family's bill, the insurer's
settlement letter, their policy and their document checklist, already checked by our code.

Verdicts: needs_checking if something is unexplained or unclear; info for factual answers; cant_confirm if the facts
don't answer it or the user asks for a promise; covered / partial / not_covered only about whether a charge is payable.
Rules:
- headline at most 10 words; summary at most 70 words of simple English; use the exact rupee amounts from the facts.
- citations: for every statement, the fact ref (e.g. "F3") and a quote copied WORD FOR WORD from that fact (5-30 words).
- Never say a deduction is wrong or promise money back; say what is unclear and what to ask. No medical advice.
- toConfirm: 0-2 short things to ask the insurer or hospital.
- nextAction: "bill", "settlement", "case" (documents) or "letter" (when they should write to the insurer), else "none"."""


def answer_case_question(question: str, intent: str, log: StepLog | None = None) -> AskResponse:
    log = log or StepLog()
    case_doc = case_store.get_case()
    agent = _AGENT.get(intent, "Claim Assistant")
    log.add(agent, "Collecting your bill, settlement and checklist")

    needed = _NEEDS.get(intent)
    if needed and not case_doc.get(needed[0]):
        return AskResponse(steps=log.steps, answer=AnswerCard(
            verdict="cant_confirm", headline=f"Upload {needed[1]} first",
            summary=f"I answer from your own documents, and {needed[1]} hasn't been uploaded yet.",
            citations=[], toConfirm=[], nextAction=_NEXT["upload"]))

    case = build_case(case_doc)
    facts = build_case_facts({**case_doc, "checklist": case["checklist"]})
    log.add(agent, f"Reading {len(facts)} checked facts about your claim")
    block = "\n".join(f"[{f['ref']}] {f['text']}" for f in facts)

    response = gemini().models.generate_content(
        model=get_settings().gemini_model,
        contents=[PROMPT.format(agent=agent), f"FACTS\n{block}", f"QUESTION\n{question}"],
        config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=CaseAnswerOut, temperature=0.1),
    )
    out = response.parsed if isinstance(response.parsed, CaseAnswerOut) else CaseAnswerOut.model_validate_json(response.text)

    by_ref = {f["ref"]: f for f in facts}
    citations: list[Citation] = []
    for c in out.citations:
        fact = by_ref.get(c.ref.strip("[] "))
        if fact and quote_in_text(c.quote, fact["text"]):
            src = fact["source"]
            if not any(x.docId == src["docId"] and x.page == src["page"] and x.clause == src["clause"] for x in citations):
                citations.append(Citation(quote=c.quote, **src))

    verdict, headline, to_confirm = out.verdict, out.headline, list(out.toConfirm)
    if not citations and verdict != "cant_confirm":
        verdict, headline = "cant_confirm", "I couldn't confirm this from your documents"
        to_confirm.insert(0, "Ask the insurer or hospital directly and keep their reply in writing.")
    log.add("Verifier", f"Checked sources: {len(citations)} of {len(out.citations)} quotes found in your documents")
    return AskResponse(steps=log.steps, answer=AnswerCard(
        verdict=verdict, headline=headline, summary=out.summary, citations=citations,
        toConfirm=to_confirm[:3], nextAction=_NEXT.get(out.nextAction)))
