"""Bill review: the family's corrections replace what was read, and the checks re-run on them (pure Python)."""
import unittest

from app.services.bill_checks import analyse_bill
from app.services.bill_review import apply_review, extraction_from_bill

EXTRACTION = {
    "hospital": "City Care Hospitl", "billNumber": "B-1", "billDate": "2026-08-22", "patientName": "Kamla",
    "admissionDate": "2026-08-18", "dischargeDate": "2026-08-22", "statedTotal": 1500, "unreadableLines": 1,
    "pageMarkers": [{"pdfPage": 1, "printedPage": 1, "printedTotal": 2}],
    "items": [{"description": "Room rent", "category": "room", "amount": 1000, "rate": 500, "qty": 2, "page": 1, "date": None},
              {"description": "Gloves", "category": "consumables", "amount": 300, "rate": None, "qty": None, "page": 1, "date": None}],
}


class ApplyReviewTests(unittest.TestCase):
    def test_corrections_replace_the_reading(self):
        review = {"hospital": "City Care Hospital", "patientName": "Kamala", "statedTotal": 1500,
                  "items": [{"description": " Room rent ", "category": "room", "amount": 1000, "rate": 500, "qty": 2, "page": 1},
                            {"description": "Gloves", "category": "consumables", "amount": 300, "page": 1},
                            {"description": "Doctor visit", "category": "doctor", "amount": 200, "page": 2},
                            {"description": "   ", "category": "other", "amount": 50, "page": 1}]}
        out = apply_review(EXTRACTION, review)
        self.assertEqual((out["hospital"], out["patientName"], out["billNumber"]), ("City Care Hospital", "Kamala", "B-1"))
        self.assertEqual([i["description"] for i in out["items"]], ["Room rent", "Gloves", "Doctor visit"])
        self.assertEqual(out["pageMarkers"], EXTRACTION["pageMarkers"])
        self.assertEqual(out["unreadableLines"], 1)

    def test_empty_values_clear_a_field(self):
        self.assertIsNone(apply_review(EXTRACTION, {"billNumber": ""})["billNumber"])

    def test_checks_rerun_on_the_corrected_lines(self):
        before = analyse_bill(EXTRACTION, 1)
        self.assertTrue(any(c["kind"] == "total_mismatch" for c in before["checks"]))
        fixed = apply_review(EXTRACTION, {"items": [*EXTRACTION["items"], {"description": "Doctor visit", "category": "doctor", "amount": 200, "page": 1}]})
        after = analyse_bill(fixed, 1)
        self.assertFalse(any(c["kind"] == "total_mismatch" for c in after["checks"]))
        self.assertTrue(any(c["kind"] == "missing_pages" for c in after["checks"]))


class ExtractionFromBillTests(unittest.TestCase):
    def test_rebuilds_items_header_and_page_markers(self):
        bill = {"hospital": "H", "billNumber": "1", "billDate": "2026-01-01", "total": 500, "pagesExpected": 3, "missingPages": [2],
                "items": [{"id": "b1", "description": "X", "category": "other", "amount": 500, "page": 1, "tag": "likely_payable"}]}
        out = extraction_from_bill(bill, {"patientName": "P", "admissionDate": "2026-01-01"})
        self.assertEqual([m["printedPage"] for m in out["pageMarkers"]], [1, 3])
        self.assertEqual(out["items"][0]["description"], "X")
        self.assertNotIn("tag", out["items"][0])
        self.assertEqual((out["statedTotal"], out["patientName"]), (500, "P"))
        missing = analyse_bill(out, 1)["missingPages"]
        self.assertEqual(missing, [2])


if __name__ == "__main__":
    unittest.main()
