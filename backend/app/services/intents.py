"""Keyword routing for the Claim Copilot – the fallback when the Gemini router is unavailable. Pure Python."""

INTENTS = ("policy", "bill", "settlement", "documents", "cashless_query")

# Checked in this order; the first intent with a matching keyword wins, otherwise "policy".
_KEYWORDS = (
    ("settlement", ("deduct", "settle", "approved amount", "disallow", "cut from", "less than i claimed", "paid less", "rejected", "rejection", "repudiat")),
    ("cashless_query", ("query", "pre-auth", "preauth", "pre auth", "pre-authoris", "pre-authoriz", "tpa asked", "insurer asked", "cashless")),
    ("documents", ("document", "papers", "checklist", "claim form", "what do i need to submit", "missing")),
    ("bill", ("bill", "charge", "invoice", "out of pocket", "out-of-pocket", "pay from my pocket", "non-payable", "non payable", "estimate")),
)


def keyword_intent(question: str) -> str:
    q = question.lower()
    for intent, words in _KEYWORDS:
        if any(w in q for w in words):
            return intent
    return "policy"
