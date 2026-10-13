"""ADK Policy Specialist on its own, for trying in `adk web` (run from backend/agents)."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google.adk.agents import Agent

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))
load_dotenv(BACKEND / ".env")

from app.agent_tools import policy_summary, search_policy, waiting_period_status  # noqa: E402


root_agent = Agent(
    name="policy_specialist",
    model=os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite"),
    description="Explains the family's own health-insurance policy with page and clause citations.",
    instruction=(
        "You help Indian families understand their own health policy in simple English. "
        "Always call search_policy before answering a coverage question, and waiting_period_status for anything about "
        "waiting periods or pre-existing diseases. Quote the exact words and give the page and clause for every claim you make. "
        "If the clauses don't answer the question, say you can't confirm it. Never promise approval or a payout amount, "
        "and never give medical advice."
    ),
    tools=[search_policy, waiting_period_status, policy_summary],
)
