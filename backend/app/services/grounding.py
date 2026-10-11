"""Checks that a quoted sentence really appears in the document (the grounding check). Pure Python."""
import re

_RUPEE = re.compile(r"₹|\brs\.?|\binr\b", re.IGNORECASE)
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_ELLIPSIS = re.compile(r"\.{3}|…")


def normalize(text: str) -> str:
    text = _RUPEE.sub(" rs ", text.lower())
    return " ".join(_NON_ALNUM.sub(" ", text).split())


def quote_in_text(quote: str, text: str) -> bool:
    """True if every part of the quote (split at "...") with 3+ words appears in the text, ignoring case and punctuation."""
    haystack = normalize(text)
    parts = [normalize(p) for p in _ELLIPSIS.split(quote)]
    parts = [p for p in parts if len(p.split()) >= 3]
    return bool(parts) and all(p in haystack for p in parts)


def locate_quote(quote: str, pages: dict[int, str], hint_page: int | None = None) -> int | None:
    """Page number where the quote appears, checking the cited page first. None if it appears nowhere."""
    if hint_page in pages and quote_in_text(quote, pages[hint_page]):
        return hint_page
    for number in sorted(pages):
        if number != hint_page and quote_in_text(quote, pages[number]):
            return number
    return None
