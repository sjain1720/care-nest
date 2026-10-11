"""Google ADK multi-agent Claim Copilot: a root agent that hands over to three specialists sharing app/agent_tools.

Used by `adk web` (backend/agents/claim_copilot) and the experimental POST /api/copilot/agent endpoint.
"""
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app import agent_tools as t
from app.core.config import get_settings

MODEL = get_settings().gemini_model
RULES = ("Use simple English. Base every statement on tool results and give the page/clause or bill page when you have it. "
         "If the tools don't answer the question, say you can't confirm it. Never promise approval or a payout, never say "
         "the insurer is wrong, and never give medical advice.")

policy_specialist = Agent(
    name="policy_specialist", model=MODEL,
    description="Answers what the family's own policy covers: waiting periods, limits, exclusions, co-pay, sub-limits.",
    instruction="You explain the family's health policy. Call search_policy for coverage questions and "
                "waiting_period_status for waiting periods or pre-existing diseases. Quote the exact words. " + RULES,
    tools=[t.search_policy, t.waiting_period_status, t.policy_summary],
)

bill_analyst = Agent(
    name="bill_analyst", model=MODEL,
    description="Explains the checked hospital bill and the insurer's settlement deductions or rejection.",
    instruction="You explain the hospital bill check and the settlement. Call bill_check_summary and settlement_breakdown, "
                "and search_policy when a deduction refers to a policy rule. Separate what is explained from what is not. " + RULES,
    tools=[t.bill_check_summary, t.settlement_breakdown, t.search_policy],
)

claim_assistant = Agent(
    name="claim_assistant", model=MODEL,
    description="Helps prepare and follow up a claim: documents still needed, where to get them, and escalation steps.",
    instruction="You help the family prepare and follow up their claim. Call document_checklist for papers and "
                "escalation_steps when they want to complain or appeal. Give clear next steps. " + RULES,
    tools=[t.document_checklist, t.escalation_steps],
)

root_agent = Agent(
    name="claim_copilot", model=MODEL,
    description="CareNest Claim Copilot for Indian families with health insurance.",
    instruction="You are CareNest's Claim Copilot. Work out where the family is in their hospital journey and transfer to "
                "the right specialist: policy_specialist for what the policy covers, bill_analyst for the bill or the "
                "insurer's deductions, claim_assistant for documents, submitting a claim or escalating. Answer greetings "
                "yourself in one line. " + RULES,
    sub_agents=[policy_specialist, bill_analyst, claim_assistant],
)

_sessions = InMemorySessionService()
_runner = Runner(agent=root_agent, app_name="carenest", session_service=_sessions)


async def run_copilot_agent(question: str) -> dict:
    """Runs one question through the agent team. Returns the final text and the steps (hand-overs and tool calls)."""
    session = await _sessions.create_session(app_name="carenest", user_id="demo")
    message = types.Content(role="user", parts=[types.Part(text=question)])
    steps, text = [], ""
    async for event in _runner.run_async(user_id="demo", session_id=session.id, new_message=message):
        for call in event.get_function_calls() or []:
            if call.name == "transfer_to_agent":
                steps.append({"agent": event.author, "label": f"Handing over to {(call.args or {}).get('agent_name', 'a specialist')}"})
            else:
                steps.append({"agent": event.author, "label": f"Using tool {call.name}"})
        if event.is_final_response() and event.content and event.content.parts:
            text = "".join(p.text or "" for p in event.content.parts)
    return {"steps": steps, "text": text}
