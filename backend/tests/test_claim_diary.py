"""Claim diary: stage from the latest entry, case output, and the grievance letter using the diary."""
import unittest
from datetime import date

from app.services.case_builder import build_case
from app.services.claim_tracker import sorted_timeline, stage_from_timeline
from app.services.letters import letter_facts

TODAY = date(2026, 10, 12)


def ev(kind, when, **extra):
    return {"id": f"ev-{kind[:4]}{when[-2:]}", "kind": kind, "date": when, **extra}


class StageTests(unittest.TestCase):
    def test_no_diary(self):
        self.assertIsNone(stage_from_timeline([], True, TODAY))

    def test_claim_sent_waiting_and_late(self):
        self.assertIn("waiting for the insurer's decision", stage_from_timeline([ev("claim_sent", "2026-10-01")], False, TODAY))
        self.assertIn("no decision yet", stage_from_timeline([ev("claim_sent", "2026-08-01")], False, TODAY))

    def test_claim_sent_ignored_once_decided(self):
        self.assertIsNone(stage_from_timeline([ev("claim_sent", "2026-09-01")], True, TODAY))

    def test_letter_waiting_then_overdue(self):
        self.assertIn("6 days ago", stage_from_timeline([ev("letter_sent", "2026-10-06")], True, TODAY))
        self.assertIn("No reply after 20 days", stage_from_timeline([ev("letter_sent", "2026-09-22")], True, TODAY))

    def test_reply_outcomes(self):
        paid = stage_from_timeline([ev("letter_sent", "2026-10-01"), ev("reply", "2026-10-10", outcome="paid_more", newApprovedAmount=217500)], True, TODAY)
        self.assertIn("pay more", paid)
        self.assertIn("2,17,500", paid)
        self.assertIn("complain", stage_from_timeline([ev("reply", "2026-10-10", outcome="no_change")], True, TODAY))
        self.assertIn("read what it says", stage_from_timeline([ev("reply", "2026-10-10", outcome="odd")], True, TODAY))

    def test_query_answered_only_counts_before_decision(self):
        events = [ev("letter_sent", "2026-10-06"), ev("query_answered", "2026-10-10")]
        self.assertIn("Waiting for the insurer's reply", stage_from_timeline(events, True, TODAY))
        self.assertIn("waiting for approval", stage_from_timeline(events, False, TODAY))

    def test_complaint_levels_and_closed(self):
        self.assertIn("Bima Bharosa", stage_from_timeline([ev("complaint_filed", "2026-10-10", level=2)], True, TODAY))
        self.assertIn("Ombudsman", stage_from_timeline([ev("complaint_filed", "2026-10-10", level=3)], True, TODAY))
        self.assertTrue(stage_from_timeline([ev("closed", "2026-10-11")], True, TODAY).startswith("Closed"))

    def test_outcome_note_preserves_waiting_and_closed_state(self):
        from app.services.claim_history import workflow_state
        note = ev("outcome_recorded", "2026-10-12", note="Payment not received")
        sent = ev("letter_sent", "2026-10-10")
        self.assertIn("Waiting for the insurer", stage_from_timeline([sent, note], True, TODAY))
        self.assertTrue(workflow_state({"timeline": [sent, note]})["awaitingReply"])
        closed = ev("closed", "2026-10-11")
        self.assertTrue(workflow_state({"timeline": [closed, note]})["closed"])
        self.assertTrue(stage_from_timeline([closed, note], True, TODAY).startswith("Closed"))
        self.assertIsNone(stage_from_timeline([note], True, TODAY))

    def test_outcome_note_does_not_change_financial_amounts(self):
        from app.schemas import TimelineEventIn
        from app.services.claim_history import summarize_case
        entry = TimelineEventIn(kind="outcome_recorded", date="2026-10-12", note="Payment received, awaiting clarification")
        case = {"settlement": {"claimedAmount": 100, "approvedAmount": 80}, "timeline": [entry.model_dump()]}
        summary = summarize_case(case, "review-test")
        self.assertFalse(summary["closed"])
        self.assertEqual(summary["approvedAmount"], 80)

    def test_sorted_by_date_stable(self):
        events = [ev("reply", "2026-10-10"), ev("letter_sent", "2026-10-01"), ev("closed", "2026-10-10")]
        self.assertEqual([e["kind"] for e in sorted_timeline(events)], ["letter_sent", "reply", "closed"])


class CaseDiaryTests(unittest.TestCase):
    def test_case_has_timeline_rejection_and_diary_stage(self):
        case = build_case({"rejection": {"reason": "Pre-existing disease", "page": 2, "claimNumber": "CLM-9", "docUrl": "/x"},
                           "timeline": [ev("letter_sent", "2026-10-06", letterKind="reconsideration")]}, TODAY)
        self.assertEqual(case["rejection"]["reason"], "Pre-existing disease")
        self.assertEqual(len(case["timeline"]), 1)
        self.assertTrue(case["stage"].startswith("Waiting for the insurer's reply"))

    def test_without_diary_keeps_letter_stage(self):
        case = build_case({"rejection": {"reason": "x"}}, TODAY)
        self.assertTrue(case["stage"].startswith("Claim refused"))
        self.assertEqual(case["timeline"], [])
        self.assertIsNone(build_case({}, TODAY)["rejection"])

    def test_grievance_letter_uses_diary(self):
        doc = {"timeline": [ev("letter_sent", "2026-09-20", reference="GRV-77"), ev("reply", "2026-10-02", outcome="no_change")]}
        f = letter_facts("grievance", build_case(doc, TODAY), None)
        self.assertIn("on 2026-09-20 (reference GRV-77)", f["points"][0])
        self.assertIn("reply dated 2026-10-02", f["points"][0])
        no_diary = letter_facts("grievance", build_case({}, TODAY), None)
        self.assertIn("[date of your earlier letter]", no_diary["points"][0])


if __name__ == "__main__":
    unittest.main()
