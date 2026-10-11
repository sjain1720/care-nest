"""ADK Policy Specialist: the same tools as /api/copilot/ask, for trying in `adk web` (run from backend/agents)."""
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from google.adk.agents import Agent

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))
load_dotenv(BACKEND / ".env")

from app.schemas import PolicyFacts  # noqa: E402
from app.services import policy_store as store  # noqa: E402
from app.services.embeddings import embed_texts  # noqa: E402
from app.services.waiting_periods import parse_date, status  # noqa: E402


def _active() -> tuple[str, PolicyFacts] | None:
    policy_id = store.get_active_policy_id()
    doc = store.get_policy(policy_id) if policy_id else None
    if not doc or doc.get("status") != "ready":
        return None
    return policy_id, PolicyFacts.model_validate(doc["facts"])


def search_policy(question: str) -> dict:
    """Find the policy clauses most relevant to a question. Returns page, clause label and text for each."""
    active = _active()
    if not active:
        return {"error": "No policy uploaded yet."}
    hits = store.search_clauses(active[0], embed_texts([question], "RETRIEVAL_QUERY")[0], 5)
    return {"clauses": [{"page": h["page"], "clause": h["label"], "text": h["text"][:1200]} for h in hits]}


def waiting_period_status() -> dict:
    """Every waiting period in the policy with its end date and whether it is over today (computed, not guessed)."""
    active = _active()
    if not active:
        return {"error": "No policy uploaded yet."}
    today = date.today()
    return {"today": today.isoformat(), "waitingPeriods": [
        {"label": w.label, "duration": w.duration, "endDate": w.endDate, "appliesTo": w.appliesTo,
         "page": w.citation.page, "clause": w.citation.clause, **status(parse_date(w.endDate), today)}
        for w in active[1].waitingPeriods]}


def policy_summary() -> dict:
    """Key facts: insurer, plan, sum insured, members, room rent, co-pay and sub-limits."""
    active = _active()
    if not active:
        return {"error": "No policy uploaded yet."}
    f = active[1]
    return f.model_dump(include={"insurer", "planName", "sumInsured", "startDate", "members", "roomRent", "coPay", "deductible", "subLimits"})


root_agent = Agent(
    name="policy_specialist",
    model="gemini-2.5-flash",
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
