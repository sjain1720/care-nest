"""Keyword routing for the Claim Copilot – the fallback when the Gemini router is unavailable. Pure Python."""
import re

INTENTS = ("policy", "bill", "settlement", "documents", "cashless_query")

# Checked in this order; the first intent with a matching keyword wins, otherwise "policy".
_KEYWORDS = (
    ("settlement", ("deduct", "settle", "approved amount", "disallow", "cut from", "less than i claimed", "paid less", "rejected", "rejection", "repudiat")),
    ("cashless_query", ("query", "pre-auth", "preauth", "pre auth", "pre-authoris", "pre-authoriz", "tpa asked", "insurer asked", "cashless")),
    ("documents", ("document", "papers", "checklist", "claim form", "what do i need to submit", "missing")),
    ("bill", ("bill", "charge", "invoice", "out of pocket", "out-of-pocket", "pay from my pocket", "non-payable", "non payable", "estimate")),
)

# Words that tie a question to the asker's own policy, bill or claim (English and Hindi).
_MINE = re.compile(r"\b(my|mine|me|am i|i am|i'm|do i|can i|will i|should i|have i|our|we|us)\b|मेरा|मेरी|मेरे|मुझे|हमारा|हमारी", re.I)


def keyword_intent(question: str) -> str:
    q = question.lower()
    for intent, words in _KEYWORDS:
        if any(w in q for w in words):
            return intent
    return "policy"


def keyword_about(question: str) -> str:
    """"mine" when the question is about the asker's own policy, bill or claim; "general" for how insurance works."""
    return "mine" if _MINE.search(question) else "general"
