"""Unit tests for Phase 5 pure helpers. No Google calls."""
import json
import unittest

from app.services.sse import sse_event

try:  # needs pydantic: runs in Cloud Shell, skipped on a laptop without the backend packages
    from app.services.steps import StepLog
except ModuleNotFoundError:
    StepLog = None


class SseTests(unittest.TestCase):
    def test_single_data_line_and_blank_line_terminator(self):
        msg = sse_event({"type": "step", "step": {"agent": "Verifier", "label": "Line one\nline two – ₹9,500"}})
        self.assertTrue(msg.startswith("data: "))
        self.assertTrue(msg.endswith("\n\n"))
        self.assertEqual(msg.count("\n"), 2)
        self.assertEqual(json.loads(msg[6:])["step"]["label"], "Line one\nline two – ₹9,500")


@unittest.skipIf(StepLog is None, "pydantic not installed")
class StepLogTests(unittest.TestCase):
    def test_each_step_reported_immediately_in_order(self):
        seen = []
        log = StepLog(on_step=lambda s: seen.append((s.agent, s.label, len(log.steps))))
        log.add("Claim Copilot", "Understanding your question")
        log.add("Verifier", "Checked sources")
        self.assertEqual(seen, [("Claim Copilot", "Understanding your question", 1), ("Verifier", "Checked sources", 2)])
        self.assertEqual([s.label for s in log.steps], ["Understanding your question", "Checked sources"])

    def test_works_without_callback(self):
        log = StepLog()
        log.add("Policy Specialist", "Searching your policy")
        self.assertEqual(len(log.steps), 1)


if __name__ == "__main__":
    unittest.main()
