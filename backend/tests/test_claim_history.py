"""Claim list summaries (pure Python)."""
import unittest

from app.services.claim_history import archived_summary, workflow_state, claim_status, has_content, manual_claim, new_claim_id, newest_first, summarize_case

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

    def test_payment_outcome_does_not_close_a_claim(self):
        s = summarize_case({"settlement": {"claimedAmount": 100, "approvedAmount": 100}}, "current")
        self.assertEqual((s["status"], s["closed"], s["awaitingReply"]), ("paid", False, False))

    def test_pending_reply_requires_outbound_followup(self):
        self.assertFalse(workflow_state({"timeline": [{"kind": "claim_sent", "date": "2026-09-01"}]})["awaitingReply"])
        for kind in ("letter_sent", "query_answered", "complaint_filed"):
            with self.subTest(kind=kind):
                case = {"timeline": [{"kind": kind, "date": "2026-10-17"}]}
                self.assertTrue(workflow_state(case)["awaitingReply"])
                # Stable same-day ordering: the new reply ends the waiting state.
                case["timeline"].append({"kind": "reply", "date": "2026-10-17", "outcome": "asks_for_papers"})
                self.assertFalse(workflow_state(case)["awaitingReply"])
                case["timeline"].append({"kind": "letter_sent", "date": "2026-10-17"})
                self.assertTrue(workflow_state(case)["awaitingReply"])
                case["timeline"].append({"kind": "closed", "date": "2026-10-17"})
                self.assertEqual(workflow_state(case), {"closed": True, "awaitingReply": False})

    def test_later_decision_supersedes_followup(self):
        case = {"timeline": [{"kind": "query_answered", "date": "2026-09-01"}],
                "settlement": {"letterDate": "2026-09-02"}}
        self.assertFalse(workflow_state(case)["awaitingReply"])

    def test_old_archives_refresh_lifecycle_without_changing_money(self):
        saved = {"id": "cl-00000001", "closed": False, "approvedAmount": 73420}
        record = {"summary": saved, "case": {"timeline": [{"kind": "closed", "date": "2026-05-12"}]}}
        result = archived_summary(record)
        self.assertEqual((result["closed"], result["awaitingReply"], result["approvedAmount"]), (True, False, 73420))
        self.assertFalse(saved["closed"])
        self.assertFalse(archived_summary({"summary": {**saved, "closed": True}})["awaitingReply"])

    def test_manual_claim(self):
        s = manual_claim({"date": "2026-06-05", "approvedAmount": 42000, "claimedAmount": 45000, "title": "Dengue"}, "cl-0000000a")
        self.assertEqual((s["source"], s["status"], s["closed"], s["hospital"]), ("manual", "part_paid", True, ""))

    def test_newest_first(self):
        claims = [{"id": "a", "date": "2026-01-01"}, {"id": "b", "date": "2026-06-01"}, {"id": "c", "date": ""}]
        self.assertEqual([c["id"] for c in newest_first(claims)], ["b", "a", "c"])


if __name__ == "__main__":
    unittest.main()
