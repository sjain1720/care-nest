"""Regressions for issues observed against the deployed demo."""
import unittest
from unittest.mock import Mock, patch

from app.services import case_qa, copilot
from app.services.case_builder import build_case
from app.services.case_facts import build_case_facts
from tests.test_copilot_and_letters import demo_case_doc


class LiveFindingTests(unittest.TestCase):
    def test_approval_promise_is_refused_without_unrelated_citations(self):
        with patch.object(copilot, "route") as router:
            result = copilot.answer("Will my claim definitely be approved?")
        router.assert_not_called()
        self.assertEqual(result.answer.verdict, "cant_confirm")
        self.assertEqual(result.answer.citations, [])

    def test_document_requirements_retrieve_and_cite_policy(self):
        doc = {**demo_case_doc(), "policyId": "policy-test"}
        count = len(build_case_facts({**doc, "checklist": build_case(doc)["checklist"]}))
        text = "Submit the original hospital bill and all investigation reports with the claim form."
        output = case_qa.CaseAnswerOut(verdict="info", headline="Collect your claim documents", summary=text,
                                      citations=[case_qa.CiteRef(ref=f"F{count + 1}", quote=text)], toConfirm=[], nextAction="case")
        client = Mock()
        client.models.generate_content.return_value = Mock(parsed=output)
        with patch.object(case_qa.case_store, "get_case", return_value=doc), \
             patch.object(case_qa.policy_store, "get_active_policy", return_value=("policy-test", {"facts":{}})), \
             patch.object(case_qa.policy_store, "search_clauses", return_value=[{"text": text, "page": 22, "label": "Clause 7.4"}]) as search, \
             patch.object(case_qa, "embed_texts", return_value=[[1.0] * 768]), \
             patch.object(case_qa.policy_store, "load_page", return_value=text), \
             patch.object(case_qa, "check_support", return_value=True), \
             patch.object(case_qa, "gemini", return_value=client):
            result = case_qa.answer_case_question("Which papers do I submit?", "documents")
        search.assert_called_once()
        self.assertEqual(result.answer.citations[0].docId, "policy")
        self.assertEqual(result.answer.citations[0].page, 22)
        self.assertEqual(result.answer.citations[0].quote, text)
