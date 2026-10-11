"""Splits OCR page text into clauses, keeping the page each clause starts on. Pure Python (no Google calls)."""
import re
from dataclasses import dataclass

# "Clause 4.2 ...", "Section 3 - ...", "Annexure II ...", or a bare number like "4.2 Specific illnesses".
_HEADING = re.compile(
    r"^\s*(?:(?P<kw>clause|section|annexure|annex|schedule|part)\s+(?P<kwnum>[0-9IVXLC]+(?:\.\d+)*)"
    r"|(?P<num>\d+(?:\.\d+)+))(?=[\s.:\-–]|$)[\s.:\-–]*(?P<title>.*)$",
    re.IGNORECASE,
)
MAX_CHARS = 1500
# Table-of-contents lines end in dot leaders and a page number: "Annexure II  Non-payable items ....... 38".
_TOC_LINE = re.compile(r"(?:\.\s*){4,}\d+\s*$")


@dataclass
class Clause:
    clause_id: str
    page: int
    label: str
    title: str
    text: str


def heading_label(line: str) -> tuple[str, str] | None:
    """Return (label, title) if the line starts a clause, e.g. ("Clause 4.2", "Specific illnesses")."""
    m = _HEADING.match(line)
    if not m or _TOC_LINE.search(line):
        return None
    title = m["title"].strip()[:90]
    if m["kw"]:
        kw = m["kw"].lower()
        kw = "Annexure" if kw in ("annex", "annexure") else kw.capitalize()
        return f"{kw} {m['kwnum'].upper()}", title
    return f"Clause {m['num']}", title


def _chunks(text: str) -> list[str]:
    if len(text) <= MAX_CHARS:
        return [text]
    parts, current = [], ""
    for para in re.split(r"\n\s*\n|\n", text):
        if current and len(current) + len(para) + 1 > MAX_CHARS:
            parts.append(current)
            current = ""
        current = f"{current}\n{para}" if current else para
        while len(current) > MAX_CHARS:
            parts.append(current[:MAX_CHARS])
            current = current[MAX_CHARS:]
    if current.strip():
        parts.append(current)
    return parts


def split_into_clauses(pages: list[dict]) -> list[Clause]:
    """pages: [{"page": 1, "text": "..."}]. A clause that runs onto the next page continues under the same label."""
    clauses: list[Clause] = []
    label, title = None, ""

    def flush(page_no: int, lines: list[str], cur_label: str, cur_title: str) -> None:
        text = "\n".join(lines).strip()
        for part in _chunks(text) if text else []:
            idx = sum(1 for c in clauses if c.page == page_no) + 1
            clauses.append(Clause(f"p{page_no:03d}-c{idx:02d}", page_no, cur_label, cur_title, part))

    for page in sorted(pages, key=lambda p: p["page"]):
        n = page["page"]
        buf: list[str] = []
        cur_label, cur_title = label or f"Page {n}", title
        for line in page["text"].splitlines():
            h = heading_label(line)
            if h:
                flush(n, buf, cur_label, cur_title)
                buf = []
                cur_label, cur_title = h
                label, title = h
            buf.append(line)
        flush(n, buf, cur_label, cur_title)
    return clauses
