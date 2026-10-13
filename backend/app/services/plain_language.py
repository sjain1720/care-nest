"""One writing style for every AI answer: plain words, short sentences and a clear next step."""

STYLE = """
How to write (the reader is a worried family member, not an insurance expert):
- Talk to the reader as "you". Short sentences of at most 15 words. Everyday words. Active voice.
- Start with the answer. Then give the one reason that matters most.
- Avoid insurance jargon. If a term is needed, explain it in brackets the first time, for example:
  "co-pay (the share you pay yourself)", "waiting period (time before cover starts)",
  "TPA (the company that handles claims for the insurer)", "sub-limit (a cap for one treatment)",
  "non-payable item (something the insurer never pays for)", "settlement letter (the insurer's letter saying what it paid)".
- Write rupees as ₹12,345 and dates as 12 Mar 2026.
- Tell the reader what to do next. Each next step starts with a verb, e.g. "Ask the hospital for…"."""

NEXT_STEPS = ("toConfirm: 1-3 next steps for the family, in order. Each starts with a verb (Ask, Collect, Upload, Check, "
              "Send) and has at most 15 words.")

LANGUAGES = {"en": "English", "hi": "Hindi"}


def language_rule(language: str) -> str:
    """Extra instruction for answers in a language other than English. Quotes stay word for word so they can be verified."""
    if language not in LANGUAGES or language == "en":
        return ""
    return (f"\nLanguage: write the headline, summary and toConfirm in simple {LANGUAGES[language]} "
            f"(Devanagari script for Hindi). Keep rupee amounts, dates, page and clause numbers as digits. "
            "Copy every quote exactly as it appears in the document, in the document's own language.")
