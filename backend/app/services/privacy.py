"""Masks personal details in free text before it is stored. Pure Python."""
import re

_PATTERNS = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[email]"),
    (re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)"), "[phone]"),
    (re.compile(r"(?<!\d)\d{4}[\s-]\d{4}[\s-]\d{4}(?!\d)"), "[id number]"),
    (re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"), "[id number]"),
]


def mask_pii(text: str | None) -> str | None:
    if not text:
        return text
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def mask_all(value):
    """Applies mask_pii to every string inside nested dicts and lists."""
    if isinstance(value, str):
        return mask_pii(value)
    if isinstance(value, list):
        return [mask_all(v) for v in value]
    if isinstance(value, dict):
        return {k: mask_all(v) for k, v in value.items()}
    return value
