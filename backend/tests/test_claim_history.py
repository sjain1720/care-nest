"""Claim list summaries (pure Python)."""
import unittest

from app.services.claim_history import claim_status, has_content, manual_claim, new_claim_id, newest_first, summarize_case

CASE = {
    "billHeader": {"patientName": "Kamala Sharma", "diagnosis": "Gallbladder surgery", "admissionDate": "2026-08-18", "dischargeDate": "2026-08-22"},
    "bill": {"hospital": "City Care Hospital", "total": 246000, "billDate": "2026-08-22"},
    "settlement": {"claimNumber": "CLM-1", "letterDate": "2026-09-20", "claimedAmount": 246000, "approvedAmount": 208000},
    "documents": [{"id": "doc-0123456789abcdef", "type": "Hospital bill"}],
}


class ClaimHistoryTests(unittest.TestCase):
    def test_ids(self):
        self.assertRegex(new_claim_id(), r"^cl-[0-9a-f]{8}$")

    def test_empty_claim_has_no_content(self):
        self.assertFalse(has_content({"id": "current"}))
        self.assertFalse(has_content({"documents": [], "timeline": []}))
        self.assertTrue(has_content({"timeline": [{"kind": "claim_sent", "date": "2026-09-01"}]}))

    def test_status(self):
        self.assertEqual(claim_status(None, None), "in_progress")
        self.assertEqual(claim_status(1000, 0), "refused")
        self.assertEqual(claim_status(1000, 800), "part_paid")
        self.assertEqual(claim_status(1000, 1000), "paid")
        self.assertEqual(claim_status(None, 500), "paid")

    def test_summary_of_a_settled_claim(self):
        s = summarize_case(CASE, "current")
        self.assertEqual((s["title"], s["patient"], s["hospital"], s["date"]), ("Gallbladder surgery", "Kamala Sharma", "City Care Hospital", "2026-08-22"))
        self.assertEqual((s["claimedAmount"], s["approvedAmount"], s["status"], s["claimNumber"]), (246000, 208000, "part_paid", "CLM-1"))
        self.assertFalse(s["closed"])

    def test_reply_that_pays_more_wins(self):
        case = {**CASE, "timeline": [{"kind": "reply", "date": "2026-10-01", "outcome": "paid_more", "newApprovedAmount": 246000},
                                     {"kind": "closed", "date": "2026-10-05"}]}
        s = summarize_case(case, "cl-00000000")
        self.assertEqual((s["approvedAmount"], s["status"]), (246000, "paid"))
        self.assertTrue(s["closed"])

    def test_refused_and_undecided(self):
        refused = summarize_case({"rejection": {"claimNumber": "CLM-2", "letterDate": "2026-05-02"}}, "x")
        self.assertEqual((refused["approvedAmount"], refused["status"], refused["date"]), (0, "refused", "2026-05-02"))
        pending = summarize_case({"bill": {"total": 50000, "billDate": "2026-09-01"}}, "x")
        self.assertEqual((pending["approvedAmount"], pending["status"]), (None, "in_progress"))

    def test_manual_claim(self):
        s = manual_claim({"date": "2026-06-05", "approvedAmount": 42000, "claimedAmount": 45000, "title": "Dengue"}, "cl-0000000a")
        self.assertEqual((s["source"], s["status"], s["closed"], s["hospital"]), ("manual", "part_paid", True, ""))

    def test_newest_first(self):
        claims = [{"id": "a", "date": "2026-01-01"}, {"id": "b", "date": "2026-06-01"}, {"id": "c", "date": ""}]
        self.assertEqual([c["id"] for c in newest_first(claims)], ["b", "a", "c"])


if __name__ == "__main__":
    unittest.main()
