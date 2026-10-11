"""Unit tests for merging user-entered schedule details. Run from backend/:  python -m unittest discover -s tests -t ."""
import unittest

from app.services.policy_details import PRODUCT_NOTES, apply_user_details, format_inr


def wording_only_facts() -> dict:
    """Facts as read from a policy wording that has no schedule (no start date, sum insured or members)."""
    return {
        "policyId": "pol-x", "policyNumber": "Not found", "sumInsured": 0, "startDate": "", "members": [],
        "roomRent": {"label": "Room-rent limit not found in your document"},
        "waitingPeriods": [
            {"id": "wp-1", "label": "Initial", "kind": "initial", "duration": "30 days", "startDate": "", "endDate": "",
             "appliesTo": "All illnesses", "citation": {"page": 9, "clause": "Clause 4.1", "quote": "q"}},
            {"id": "wp-2", "label": "Pre-existing", "kind": "ped", "duration": "36 months", "startDate": "", "endDate": "",
             "appliesTo": "Declared", "citation": {"page": 9, "clause": "Clause 4.3", "quote": "q"}},
        ],
        "flags": [{"kind": "ambiguous", "code": "missing_start_date", "message": "No start date"},
                  {"kind": "missing_pages", "message": "Annexure III missing"}],
    }


class ApplyDetailsTests(unittest.TestCase):
    def test_start_date_fills_waiting_periods_and_clears_flag(self):
        facts = apply_user_details(wording_only_facts(), {"startDate": "2024-03-12"})
        self.assertEqual([w["endDate"] for w in facts["waitingPeriods"]], ["2024-04-11", "2027-03-12"])
        self.assertEqual([f["kind"] for f in facts["flags"]], ["missing_pages"])
        self.assertEqual(facts["userProvided"], ["startDate"])

    def test_room_rent_and_members(self):
        facts = apply_user_details(wording_only_facts(), {
            "roomRentPerDay": 5000, "sumInsured": 500000,
            "members": [{"name": "Mohan", "relation": "Father", "age": 62}],
        })
        self.assertEqual(facts["roomRent"]["amount"], 5000)
        self.assertIn("₹5,000 per day", facts["roomRent"]["label"])
        self.assertEqual(facts["members"][0]["age"], 62)
        self.assertEqual(set(facts["userProvided"]), {"roomRentPerDay", "sumInsured", "members"})

    def test_room_label_from_document_is_kept(self):
        base = wording_only_facts()
        base["roomRent"] = {"label": "1% of sum insured", "citation": {"page": 7, "clause": "Clause 3.2", "quote": "q"}}
        facts = apply_user_details(base, {"roomRentPerDay": 5000})
        self.assertEqual(facts["roomRent"]["label"], "1% of sum insured")

    def test_base_is_not_changed_and_empty_details_do_nothing(self):
        base = wording_only_facts()
        facts = apply_user_details(base, {})
        self.assertEqual(base["startDate"], "")
        self.assertEqual(facts["userProvided"], [])
        self.assertEqual(facts["waitingPeriods"], base["waitingPeriods"])


class FormatTests(unittest.TestCase):
    def test_indian_grouping(self):
        self.assertEqual(format_inr(500000), "₹5,00,000")
        self.assertEqual(format_inr(12345678), "₹1,23,45,678")
        self.assertEqual(format_inr(950), "₹950")

    def test_every_product_type_has_note_entry(self):
        self.assertIsNone(PRODUCT_NOTES["health_indemnity"])
        for key in ("travel", "hospital_cash", "critical_illness", "personal_accident", "other"):
            self.assertTrue(PRODUCT_NOTES[key])


if __name__ == "__main__":
    unittest.main()
