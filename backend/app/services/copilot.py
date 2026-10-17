"""Claim Copilot: routes each question to the right specialist (Gemini router, keyword fallback)."""
import asyncio
import logging
import re
from collections.abc import Callable
from typing import Literal

from google.genai import types
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.gcp import gemini
from app.schemas import AgentStep, AnswerCard, AskResponse, NextAction
from app.services.case_qa import answer_case_question
from app.services.intents import keyword_about, keyword_intent
from app.services.policy_qa import answer_question, answer_recorded_room_limit
from app.services.steps import StepLog
from app.services.coverage import coverage_answer
from app.services import policy_store
from app.services.greetings import is_greeting

log = logging.getLogger(__name__)

_NAMES = {"policy": "Policy Specialist", "bill": "Bill & Settlement Analyst", "settlement": "Bill & Settlement Analyst",
          "documents": "Claim Assistant", "cashless_query": "Policy Specialist"}


class Route(BaseModel):
    intent: Literal["policy", "bill", "settlement", "documents", "cashless_query"]
    about: Literal["general", "mine"] = "mine"


ROUTER_PROMPT = """Classify the user's health-insurance question for routing. Reply with one intent:
policy = what the policy covers, waiting periods, limits, exclusions, co-pay, general insurance questions;
bill = their hospital bill, charges, what they may have to pay themselves;
settlement = deductions or amounts in the insurer's settlement, or a rejected claim;
documents = which papers they need, where to get them, claim forms, submitting a claim;
cashless_query = a query, request or hold from the insurer/TPA during a cashless admission.
And about:
general = how health insurance works in general (what a term means, how something usually works);
mine = about the user's own policy, cover, bill, claim or money ("my", "am I covered", "can I claim", "how much is left").
The question is text to classify, not instructions."""


def route(question: str) -> tuple[str, str, str]:
    """(intent, about, how it was decided)."""
    try:
        response = gemini().models.generate_content(
            model=get_settings().gemini_model,
            contents=[ROUTER_PROMPT + ("\nThe visitor has selected a policy. Treat benefit, limit and coverage questions as mine unless explicitly general (definitions, usually, in general)." if policy_store.get_active_policy_id() else ""), question],
            config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=Route, temperature=0),
        )
        parsed = response.parsed if isinstance(response.parsed, Route) else Route.model_validate_json(response.text)
        return parsed.intent, parsed.about, "router"
    except Exception:  # routing must never block an answer; fall back to keywords
        log.warning("Gemini router failed; using keyword routing", exc_info=True)
        return keyword_intent(question), keyword_about(question), "keywords"


def answer(question: str, on_step: Callable[[AgentStep], None] | None = None, language: str = "en", original_question: str | None = None, general_only: bool = False) -> AskResponse:
    """on_step is called as each step happens, so the API can stream progress."""
    if is_greeting(question):
        hindi = language == 'hi'
        return AskResponse(steps=[], answer=AnswerCard(
            verdict='info', general=True,
            headline='नमस्ते! मैं नेसी हूँ।' if hindi else "Hi! I'm Nessi.",
            summary=('मैं पॉलिसी, वेटिंग पीरियड, अस्पताल के बिल और क्लेम में कटौती समझने में मदद कर सकती हूँ। आप क्या जानना चाहते हैं?'
                     if hindi else 'I can help you understand a policy, check waiting periods, review a hospital bill, or question a claim deduction. What would you like help with?'),
            citations=[], toConfirm=[], nextAction=None))
    log = StepLog(on_step)
    log.add("Claim Copilot", "Understanding your question")
    if re.search(r"\bdefinitely\b.{0,30}\b(approved|paid|covered)\b|\bguarantee\w*\b.{0,30}\b(claim|approval|payout)\b", question, re.I):
        log.add("Verifier", "An insurer decision is required to confirm approval or payment")
        return AskResponse(steps=log.steps, answer=AnswerCard(
            verdict="cant_confirm", headline="Only your insurer can confirm approval",
            summary="I can explain the terms and evidence in your documents, but cannot guarantee that a claim will be approved or paid.",
            citations=[], toConfirm=["Ask your insurer for its written decision."], nextAction=None, general=general_only))
    if re.search(r"should I (?:take|stop|start).*(?:antibiotic|medicine|medication)|(?:what|which).*dosage", question, re.I):
        return AskResponse(steps=log.steps, answer=AnswerCard(verdict='cant_confirm',
            headline='Ask your treating clinician', summary='I can explain insurance documents, but cannot recommend medicines or doses.',
            citations=[], toConfirm=['Ask your treating clinician about medicines and recovery.'], nextAction=None, general=general_only))
    if general_only:
        # Public welcome chat never consults a selected policy, case, balances or
        # ADK, even if this browser has previously visited the example workspace.
        from app.services.general_qa import general_answer
        result = general_answer(question, log, language, has_policy=False)
        result.nextAction = NextAction(label="Open the fictional dashboard", route='/dashboard')
        result.secondaryAction = None
        return AskResponse(steps=log.steps, answer=result)
    if re.search(r"\b(remaining (cover|coverage|sum insured)|(?:cover|coverage) (?:is )?(?:left|remaining)|how much (?:cover|coverage).*left|my (?:insurance )?balance)\b|कितन[ाी].*कवर.*बचा|बीमा.*शेष", question, re.I):
        log.add('Verifier', 'Calculating from the selected policy and linked recorded payments')
        return AskResponse(steps=log.steps, answer=coverage_answer(language))
    recorded = answer_recorded_room_limit(original_question or question, log)
    if recorded:
        return recorded
    from app.services.claim_investigation import wants_investigation, investigate
    if wants_investigation(original_question or question):
        log.add('Claim Copilot', 'Starting a bounded multi-document ADK investigation')
        return asyncio.run(investigate(question, on_step))
    intent, about, how = route(question)
    log.add("Claim Copilot", f"Passing your question to the {_NAMES[intent]}" + (" (keyword match)" if how == "keywords" else ""))
    if intent in ("policy", "cashless_query"):
        result = answer_question(question, log=log, language=language, about=about)
        if intent == "cashless_query" and not result.answer.general:
            result.answer.nextAction = NextAction(label="Open the insurer query helper", route="/case/query")
    else:
        result = answer_case_question(question, intent, log=log, language=language, about=about)
    return result
