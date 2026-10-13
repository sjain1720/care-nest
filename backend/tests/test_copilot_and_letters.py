"""Unit tests for Phase 4 pure logic: routing keywords, case facts, letters, checklist overrides. No Google calls."""
import unittest

from app.services.bill_checks import analyse_bill
from app.services.case_builder import build_case
from app.services.case_facts import build_case_facts
from app.services.grounding import quote_in_text
from app.services.intents import keyword_intent
from app.services.letters import amounts_in, letter_facts, template_body, unknown_amounts
from tests.test_bill_and_case import demo_bill_extraction


def demo_case_doc() -> dict:
    bill = analyse_bill(demo_bill_extraction(), 6, room_limit=5000)
    bill["docUrl"] = "/api/case/document/doc-0123456789abcdef"
    settlement = {
        "claimNumber": "CLM-2026-0083412", "claimedAmount": 246000, "approvedAmount": 208000,
        "deductions": [
            {"id": "d1", "label": "Room-rent and proportionate deduction", "amount": 21600, "trust": "supported",
             "insurerReason": "Room category exceeds eligibility.", "ourReading": "Matches the clause.",
             "calculation": ["Room rent: 4 days × (₹7,500 − ₹5,000) = ₹10,000"],
             "citations": [{"docId": "policy", "docName": "Policy wording", "page": 11, "clause": "Clause 5.3", "quote": "payable in the same proportion"},
                           {"docId": "settlement", "docName": "Settlement letter", "page": 2, "clause": "Deductions", "quote": "Room: ₹21,600", "docUrl": "/x"}]},
            {"id": "d2", "label": "Other deductions", "amount": 9500, "trust": "unknown", "insurerReason": "No reason or clause stated.",
             "ourReading": "No reason given.", "calculation": [], "citations": []},
        ],
    }
    return {"bill": bill, "settlement": settlement, "billHeader": {"patientName": "Kamala Sharma"},
            "documents": [{"id": "doc-0123456789abcdef", "name": "bill.pdf", "type": "Hospital bill", "pages": 6, "uploadedOn": "2026-10-11"}]}


class IntentTests(unittest.TestCase):
    def test_routes(self):
        self.assertEqual(keyword_intent("Why was ₹38,000 deducted?"), "settlement")
        self.assertEqual(keyword_intent("The TPA sent a query on my pre-auth"), "cashless_query")
        self.assertEqual(keyword_intent("Which documents am I missing?"), "documents")
        self.assertEqual(keyword_intent("How much will I pay out of pocket on this bill?"), "bill")
        self.assertEqual(keyword_intent("Is cataract covered?"), "policy")


class CaseFactsTests(unittest.TestCase):
    def setUp(self):
        doc = demo_case_doc()
        doc["checklist"] = build_case(doc)["checklist"]
        self.facts = build_case_facts(doc)

    def test_refs_and_sources(self):
        self.assertEqual(self.facts[0]["ref"], "F1")
        self.assertTrue(all(f["source"]["page"] >= 1 for f in self.facts))

    def test_key_facts_present_and_quotable(self):
        texts = " ".join(f["text"] for f in self.facts)
        self.assertIn("most likely ₹28,500", texts)
        self.assertIn("deducted ₹31,100", texts)
        policy = [f for f in self.facts if f["source"]["docId"] == "policy"]
        self.assertEqual(policy[0]["source"]["clause"], "Clause 5.3")
        self.assertTrue(quote_in_text("approved ₹2,08,000, deducted", self.facts[[f["text"].startswith("Settlement") for f in self.facts].index(True)]["text"]))

    def test_missing_documents_listed(self):
        self.assertTrue(any(f["text"].startswith("Still needed: Discharge summary") for f in self.facts))


class LetterTests(unittest.TestCase):
    def setUp(self):
        doc = demo_case_doc()
        self.case = {**build_case(doc), "settlement": doc["settlement"], "bill": doc["bill"]}

    def test_clarification_unexplained_first(self):
        f = letter_facts("clarification", self.case, {"insurer": "Suraksha (demo)", "policyNumber": "XXXX-4821"})
        self.assertIn("Grievance Officer, Suraksha (demo)", f["to"])
        self.assertIn("Other deductions – ₹9,500: no reason", f["points"][1])
        self.assertIn("Clause 5.3", f["points"][2])
        self.assertIn("Policy wording – Clause 5.3 (page 11)", f["evidenceIndex"])
        self.assertTrue({246000, 208000, 31100, 21600, 9500} <= set(f["allowedAmounts"]))

    def test_template_body_uses_only_allowed_amounts(self):
        f = letter_facts("clarification", self.case, None)
        body = template_body(f)
        self.assertEqual(unknown_amounts(body, set(f["allowedAmounts"])), [])
        self.assertIn("Policy number: [policy number]", body)

    def test_invented_amount_detected(self):
        self.assertEqual(unknown_amounts("We ask for ₹9,500 and Rs. 12,000 back", {9500}), [12000])
        self.assertEqual(amounts_in("INR 2,46,000 and ₹950.50"), {246000, 950})

    def test_cover_letter_lists_documents(self):
        f = letter_facts("cover_letter", self.case, None)
        self.assertIn("Enclosed: Final hospital bill, with every charge listed", f["points"])
        self.assertTrue(any(p.startswith("To follow:") for p in f["points"]))


class ChecklistOverrideTests(unittest.TestCase):
    def test_user_ticks_win(self):
        doc = demo_case_doc()
        doc["checklistStatus"] = {"c5": "collected", "c4": "missing"}
        by_id = {i["id"]: i for i in build_case(doc)["checklist"]}
        self.assertEqual(by_id["c5"]["status"], "collected")
        self.assertEqual(by_id["c4"]["status"], "missing")

    def test_rejected_stage(self):
        case = build_case({"rejection": {"reason": "Pre-existing disease", "claimNumber": "CLM-9"}})
        self.assertTrue(case["stage"].startswith("Claim refused"))
        self.assertEqual(case["claimNumber"], "CLM-9")
        self.assertIn("x-reject", {i["id"] for i in case["checklist"]})


if __name__ == "__main__":
    unittest.main()
