"""Experimental ADK bounds, lifecycle and source-integrity release checks."""
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from app import adk_copilot as adk, agent_tools


class GuardTests(unittest.TestCase):
    def test_all_specialists_share_tool_guard(self):
        for agent in (adk.root_agent, adk.policy_specialist, adk.bill_analyst, adk.claim_assistant):
            self.assertIs(agent.before_tool_callback, adk.guard_tool)

    def test_tool_limit_and_changed_scope_stop_execution(self):
        for budget, current in (({'calls': adk.MAX_TOOL_CALLS, 'scope': 'a'}, 'a'),
                                ({'calls': 0, 'scope': 'a'}, 'b')):
            token = adk._budget.set(budget)
            try:
                with patch.object(adk, 'snapshot', return_value={'scope': current}):
                    with self.assertRaises(adk.InvestigationLimit):
                        adk.guard_tool(None, {}, None)
            finally:
                adk._budget.reset(token)

    def test_unscoped_tool_execution_is_rejected(self):
        with self.assertRaises(adk.InvestigationLimit):
            adk.guard_tool(None, {}, None)

    def test_generated_readings_are_not_source_facts(self):
        case = {'policyId': 'p', 'bill': {'reviewed': True}, 'settlement': {
            'claimedAmount': 10000, 'approvedAmount': 8000,
            'deductions': [{'id': 'd', 'label': 'Other', 'amount': 2000,
                'insurerReason': 'Other deductions', 'ourReading': 'Guaranteed payable', 'trust': 'supported'}]}}
        with patch.object(agent_tools.case_store, 'get_case', return_value=case), \
             patch.object(agent_tools.policy_store, 'get_active_policy_id', return_value='p'):
            result = agent_tools.settlement_breakdown()
        self.assertNotIn('ourReading', result['deductions'][0])
        self.assertNotIn('trust', result['deductions'][0])
        self.assertEqual(result['reconciliation']['decisionDifference'], 2000)


class LifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_distinct_guests_and_failure_cleanup(self):
        service = SimpleNamespace(create_session=AsyncMock(return_value=SimpleNamespace(id='temp')),
                                  delete_session=AsyncMock())
        class FailedRunner:
            async def run_async(self, **kwargs):
                raise RuntimeError('synthetic model failure')
                yield
        with patch.object(adk, '_sessions', service), patch.object(adk, '_runner', FailedRunner()), \
             patch.object(adk, 'snapshot', return_value={'scope': 'a', 'policyId': 'p'}):
            for guest in ('a'*32, 'b'*32):
                with patch.object(adk, 'session_id', return_value=guest):
                    result = await adk.run_copilot_agent('Explain my deductions')
                self.assertEqual(result['status'], 'unavailable')
                self.assertFalse(result['verified'])
                self.assertIsNone(adk._budget.get())
        users = [call.kwargs['user_id'] for call in service.create_session.call_args_list]
        self.assertNotEqual(users[0], users[1]); self.assertNotIn('demo', users)
        self.assertEqual(service.delete_session.await_count, 2)

    async def test_timeout_is_a_safe_failure_and_deletes_session(self):
        service = SimpleNamespace(create_session=AsyncMock(return_value=SimpleNamespace(id='temp')),
                                  delete_session=AsyncMock())
        class SlowRunner:
            async def run_async(self, **kwargs):
                import asyncio
                await asyncio.sleep(1)
                yield
        with patch.object(adk, '_sessions', service), patch.object(adk, '_runner', SlowRunner()), \
             patch.object(adk, 'snapshot', return_value={'scope': 'a', 'policyId': 'p'}), \
             patch.object(adk, 'session_id', return_value='a'*32), patch.object(adk, 'TIMEOUT_SECONDS', 0.01):
            result = await adk.run_copilot_agent('Explain my deductions')
        self.assertEqual(result['status'], 'unavailable')
        service.delete_session.assert_awaited_once()
