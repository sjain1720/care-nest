"""Unit tests for the pure-Python policy logic. Run from backend/:  python -m unittest discover -s tests"""
import importlib.util
import textwrap
import unittest
from datetime import date
from pathlib import Path

from app.services.clauses import heading_label, split_into_clauses
from app.services.grounding import locate_quote, quote_in_text
from app.services.waiting_periods import add_months, end_date, parse_date, status

ROOT = Path(__file__).resolve().parents[2]


def demo_policy_pages() -> list[dict]:
    """The synthetic policy text, shaped like Document AI output (one string per page, wrapped lines)."""
    spec = importlib.util.spec_from_file_location("make_demo_pdfs", ROOT / "demo-data" / "make_demo_pdfs.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    pages = []
    for number, lines in enumerate(module.policy_pages(), 1):
        out = []
        for line in lines:
            line = line.lstrip("# ")
            out.extend(textwrap.wrap(line, 92) or [""])
        pages.append({"page": number, "text": "\n".join(out)})
    return pages


class HeadingTests(unittest.TestCase):
    def test_clause_keyword(self):
        self.assertEqual(heading_label("Clause 3.2 Room rent"), ("Clause 3.2", "Room rent"))

    def test_bare_number(self):
        self.assertEqual(heading_label("4.2 Specific illnesses")[0], "Clause 4.2")

    def test_annexure(self):
        self.assertEqual(heading_label("Annexure II - Non-payable items")[0], "Annexure II")

    def test_plain_sentence_is_not_heading(self):
        self.assertIsNone(heading_label("Room rent is payable up to 1% of the Sum Insured."))
        self.assertIsNone(heading_label("2024 was the first policy year"))

    def test_table_of_contents_line_is_not_heading(self):
        self.assertIsNone(heading_label("Annexure II  Non-payable items ................................. 38"))


class SplitTests(unittest.TestCase):
    def setUp(self):
        self.clauses = split_into_clauses(demo_policy_pages())

    def find(self, label):
        return [c for c in self.clauses if c.label == label]

    def test_room_rent_clause_on_page_7(self):
        c = self.find("Clause 3.2")
        self.assertTrue(c)
        self.assertEqual(c[0].page, 7)
        self.assertIn("1% of the Sum Insured", c[0].text)

    def test_waiting_periods_on_page_9(self):
        for label in ("Clause 4.1", "Clause 4.2", "Clause 4.3"):
            self.assertEqual(self.find(label)[0].page, 9, label)

    def test_annexure_ii_on_page_38(self):
        self.assertEqual(self.find("Annexure II")[0].page, 38)

    def test_ids_unique_and_chunks_bounded(self):
        ids = [c.clause_id for c in self.clauses]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(len(c.text) <= 1500 for c in self.clauses))


class GroundingTests(unittest.TestCase):
    def setUp(self):
        self.pages = {p["page"]: p["text"] for p in demo_policy_pages()}

    def test_exact_quote_found(self):
        quote = "payable up to 1% of the Sum Insured per day for a normal room"
        self.assertEqual(locate_quote(quote, self.pages, 7), 7)

    def test_quote_across_line_break_and_rupee_symbol(self):
        self.assertTrue(quote_in_text("payable up to ₹40,000 per eye per policy year", self.pages[14]))

    def test_wrong_page_is_corrected(self):
        self.assertEqual(locate_quote("covered only after 24 months of continuous coverage", self.pages, 7), 9)

    def test_invented_quote_rejected(self):
        self.assertIsNone(locate_quote("cataract is fully covered from day one without limits", self.pages, 9))

    def test_ellipsis_parts_must_all_match(self):
        self.assertTrue(quote_in_text("Items for which coverage is not available: gloves, PPE kit ... registration charges", self.pages[38]))
        self.assertFalse(quote_in_text("Items for which coverage is not available ... dental implants are covered", self.pages[38]))


class WaitingPeriodTests(unittest.TestCase):
    def test_matches_demo_dates(self):
        start = parse_date("12 March 2024")
        self.assertEqual(end_date(start, days=30), date(2024, 4, 11))
        self.assertEqual(end_date(start, months=24), date(2026, 3, 12))
        self.assertEqual(end_date(start, months=36), date(2027, 3, 12))

    def test_month_end_clamped(self):
        self.assertEqual(add_months(date(2024, 1, 31), 1), date(2024, 2, 29))

    def test_status(self):
        today = date(2026, 10, 11)
        self.assertTrue(status(date(2026, 3, 12), today)["over"])
        self.assertEqual(status(date(2027, 3, 12), today), {"over": False, "daysLeft": 152})


if __name__ == "__main__":
    unittest.main()
