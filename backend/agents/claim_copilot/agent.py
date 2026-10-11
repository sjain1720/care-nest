"""ADK multi-agent Claim Copilot for `adk web` (run from backend/agents). The agents live in app/adk_copilot.py."""
import sys
from pathlib import Path

from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))
load_dotenv(BACKEND / ".env")

from app.adk_copilot import root_agent  # noqa: E402,F401
