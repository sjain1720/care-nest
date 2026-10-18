"""Pure greetings need neither document access nor model orchestration."""
import re


def is_greeting(question: str) -> bool:
    # Full match prevents swallowing real questions such as 'Hi, explain my cut'.
    return bool(re.fullmatch(
        r"\s*(?:hi|hello|hey|namaste|namaskar|नमस्ते|नमस्कार|good\s+(?:morning|afternoon|evening))"
        r"(?:\s+(?:nessi|carenest))?[\s!.,?।]*", question, re.IGNORECASE))
