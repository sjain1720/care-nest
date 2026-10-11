from pathlib import Path

from dotenv import load_dotenv
from google.adk.agents import Agent

# Reuse backend/.env so ADK talks to Vertex AI in our project.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def explain_term(term: str) -> dict:
    """Return a plain-language explanation of a common health-insurance term."""
    glossary = {
        "co-payment": "The fixed share of every claim that you always pay yourself.",
        "sub-limit": "A cap on how much the policy pays for a specific item or treatment.",
        "waiting period": "Time after buying the policy before certain treatments are covered.",
        "room rent limit": "The most the policy pays per day for your hospital room.",
    }
    text = glossary.get(term.lower().strip())
    return {"term": term, "explanation": text} if text else {"term": term, "explanation": None}


root_agent = Agent(
    name="hello_agent",
    model="gemini-2.5-flash",
    description="Phase 0 test agent for CareNest.",
    instruction=(
        "You explain health-insurance terms in simple English. "
        "Call explain_term first; if it returns no explanation, give a short general one and say it is general guidance."
    ),
    tools=[explain_term],
)
