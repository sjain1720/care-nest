"""Unit tests for bill checks, settlement reconciliation, the case checklist and PII masking. No Google calls."""
import unittest

from app.rules.non_payable import match_non_payable
from app.services.bill_checks import analyse_bill, check_pages
from app.services.case_builder import build_case
from app.services.privacy import mask_all, mask_pii
from app.services.settlement_checks import bill_evidence, has_reason, reconcile


def demo_bill_extraction() -> dict:
    """The synthetic ₹2,46,000 bill from the demo case, as Gemini would return it."""
    rows = [
        ("Room rent - Deluxe single", "room", 30000, 7500, 4, 1), ("Nursing charges", "nursing", 8800, None, None, 1),
        ("Doctor visits and consultations", "doctor", 26000, None, None, 2), ("Surgeon and OT charges", "surgery", 95000, None, None, 2),
        ("Anaesthesia", "anaesthesia", 18000, None, None, 2), ("Pharmacy and medicines", "pharmacy", 32400, None, None, 3),
        ("Lab tests and imaging", "investigations", 21000, None, None, 3), ("Medical equipment charges", "equipment", 7900, None, None, 4),
        ("Gloves, PPE kit, admission kit", "consumables", 6900, None, None, 4),
    ]
    return {
        "hospital": "City Care Hospital, Pune (demo)", "billNumber": "CCH/IP/2026/5521", "statedTotal": 246000,
        "items": [{"description": d, "category": c, "amount": a, "rate": r, "qty": q, "page": p} for d, c, a, r, q, p in rows],
        "pageMarkers": [{"pdfPage": n, "printedPage": n, "printedTotal": 6} for n in range(1, 7)],
    }


class NonPayableTests(unittest.TestCase):
    def test_matches(self):
        self.assertEqual(match_non_payable("Gloves, PPE kit, admission kit"), "Gloves")
        self.assertEqual(match_non_payable("REGISTRATION CHARGES"), "Registration charges")

    def test_no_false_hits(self):
        self.assertIsNone(match_non_payable("Combination therapy injection"))
        self.assertIsNone(match_non_payable("Surgeon and OT charges"))


class BillTests(unittest.TestCase):
    def setUp(self):
        self.bill = analyse_bill(demo_bill_extraction(), pdf_pages=6, room_limit=5000, co_pay_percent=None)

    def test_room_rent_matches_demo_deduction(self):
        room = self.bill["roomRent"]
        self.assertTrue(room["overLimit"])
        self.assertEqual(room["roomCut"], 10000)
        self.assertEqual(room["narrowCut"], 11600)
        self.assertEqual(room["roomCut"] + room["narrowCut"], 21600)

    def test_estimate_range(self):
        est = self.bill["estimate"]
        self.assertEqual((est["low"], est["likely"]), (21600, 28500))
        self.assertGreater(est["high"], est["likely"])

    def test_tags(self):
        tags = {i["description"]: i["tag"] for i in self.bill["items"]}
        self.assertEqual(tags["Gloves, PPE kit, admission kit"], "possibly_non_payable")
        self.assertEqual(tags["Room rent - Deluxe single"], "needs_clarification")
        self.assertEqual(tags["Pharmacy and medicines"], "likely_payable")

    def test_clean_bill_has_no_arithmetic_or_page_issues(self):
        kinds = {c["kind"] for c in self.bill["checks"]}
        self.assertFalse(kinds & {"missing_pages", "total_mismatch", "line_arithmetic"})

    def test_line_and_total_errors_found(self):
        ext = demo_bill_extraction()
        ext["items"][0]["amount"] = 31000  # 4 x 7500 is 30000
        kinds = {c["kind"] for c in analyse_bill(ext, 6, 5000)["checks"]}
        self.assertIn("line_arithmetic", kinds)
        self.assertIn("total_mismatch", kinds)

    def test_room_limit_unknown(self):
        bill = analyse_bill(demo_bill_extraction(), 6, room_limit=None)
        self.assertIsNone(bill["roomRent"])
        self.assertIn("room_limit_unknown", {c["kind"] for c in bill["checks"]})


class PageTests(unittest.TestCase):
    def test_missing_last_page(self):
        expected, missing, checks = check_pages(
            [{"pdfPage": 1, "printedPage": 1, "printedTotal": 3}, {"pdfPage": 2, "printedPage": 2, "printedTotal": 3}], 2)
        self.assertEqual((expected, missing), (3, [3]))
        self.assertEqual(checks[0]["severity"], "high")

    def test_gap_in_middle(self):
        markers = [{"pdfPage": i, "printedPage": p, "printedTotal": 7} for i, p in enumerate([1, 2, 4, 5, 6], 1)]
        self.assertEqual(check_pages(markers, 5)[1], [3, 7])

    def test_no_markers(self):
        self.assertEqual(check_pages([], 4), (None, [], []))


class SettlementTests(unittest.TestCase):
    def setUp(self):
        self.bill = analyse_bill(demo_bill_extraction(), 6, room_limit=5000)

    def test_reconcile(self):
        deductions = [{"amount": 21600}, {"amount": 6900}, {"amount": 9500}]
        self.assertEqual(reconcile(246000, 208000, deductions), {"deductedTotal": 38000, "arithmeticOk": True, "unexplainedGap": 0})
        self.assertEqual(reconcile(246000, 200000, deductions)["unexplainedGap"], 8000)

    def test_reason_detection(self):
        self.assertFalse(has_reason("-"))
        self.assertFalse(has_reason("Other deductions"))
        self.assertTrue(has_reason("Non-medical items not payable as per Annexure II."))

    def test_room_deduction_explained_by_calculation(self):
        evidence, calc = bill_evidence(21600, self.bill)
        self.assertTrue(calc)
        self.assertIn("matches this deduction", calc[-1])

    def test_consumables_matched_to_bill_line(self):
        evidence, _ = bill_evidence(6900, self.bill)
        self.assertIn("Gloves, PPE kit, admission kit", evidence[0])

    def test_unexplained_amount_has_no_evidence(self):
        self.assertEqual(bill_evidence(9500, self.bill), ([], []))


class CaseTests(unittest.TestCase):
    def test_checklist_from_uploads(self):
        ext = demo_bill_extraction()
        ext["pageMarkers"] = [{"pdfPage": 1, "printedPage": 1, "printedTotal": 3}, {"pdfPage": 2, "printedPage": 2, "printedTotal": 3}]
        bill = analyse_bill(ext, 2, 5000)
        settlement = {"claimNumber": "CLM-1", "deductions": [{"id": "d1", "amount": 9500, "trust": "unknown"}]}
        case = build_case({"documents": [{"id": "x", "name": "Bill", "type": "Hospital bill", "pages": 2, "uploadedOn": "2026-10-11"}],
                           "bill": bill, "settlement": settlement})
        by_id = {i["id"]: i for i in case["checklist"]}
        self.assertEqual(by_id["c4"]["status"], "collected")
        self.assertEqual(by_id["c3"]["status"], "missing")
        self.assertIn("3", by_id["c4b"]["name"])
        self.assertEqual(by_id["x-d1"]["group"], "dispute")
        self.assertEqual(case["stage"], "Paid, with ₹9,500 cut")

    def test_empty_case(self):
        case = build_case({})
        self.assertEqual(case["stage"], "Add your hospital bill to start")
        self.assertEqual(len(case["escalation"]), 3)


class PrivacyTests(unittest.TestCase):
    def test_masks(self):
        text = "Call 98765 43210 or +91-9876543210, mail a.b@x.com, Aadhaar 1234 5678 9012, PAN ABCDE1234F"
        out = mask_pii(text)
        for secret in ("98765", "9876543210", "a.b@x.com", "1234 5678 9012", "ABCDE1234F"):
            self.assertNotIn(secret, out)

    def test_amounts_untouched(self):
        self.assertEqual(mask_pii("Total ₹2,46,000 for 4 days, bill CCH/IP/2026/5521"), "Total ₹2,46,000 for 4 days, bill CCH/IP/2026/5521")

    def test_nested(self):
        self.assertEqual(mask_all({"a": ["x@y.com", 5]}), {"a": ["[email]", 5]})


if __name__ == "__main__":
    unittest.main()
