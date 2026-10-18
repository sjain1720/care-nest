import asyncio
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from app.core import session
from app.core.session_middleware import GuestSessionMiddleware
from app.schemas import AnswerCard
from app.services import conversation, copilot, example_workspace


class GeneralBoundaryTests(unittest.TestCase):
    def test_general_mode_retains_deterministic_approval_and_medical_guards(self):
        with patch('app.services.general_qa.general_answer', side_effect=AssertionError('Model should not run')):
            for question in ('Guarantee my claim approval', 'What medicine dosage should I take?'):
                with self.subTest(question=question):
                    result = copilot.answer(question, general_only=True)
                    self.assertEqual(result.answer.verdict, 'cant_confirm')
                    self.assertTrue(result.answer.general)
                    self.assertEqual(result.answer.citations, [])

    def test_general_turn_never_reads_policy_case_or_routes_an_investigation(self):
        card = AnswerCard(verdict='info', headline='General guidance', summary='Limits vary.', general=True, citations=[], toConfirm=[])
        with patch('app.services.general_qa.general_answer', return_value=card), \
             patch.object(copilot.policy_store, 'get_active_policy_id', side_effect=AssertionError('Policy read')), \
             patch('app.services.case_store.get_case', side_effect=AssertionError('Case read')), \
             patch.object(copilot, 'route', side_effect=AssertionError('Router used')):
            result = copilot.answer('Investigate my claim and remaining cover', general_only=True)
            self.assertTrue(result.answer.general)
            self.assertEqual(result.answer.citations, [])
            self.assertEqual(result.answer.nextAction.route, '/upload')
            self.assertEqual(conversation.scope_key(True), 'general-insurance-v1')

    def test_example_owner_is_server_resolved_but_cookie_remains_parent(self):
        root, child = session.new_session_id(), session.new_session_id()
        deadline = datetime.now(timezone.utc) + session.TTL
        seen, sent = {}, []

        async def app(scope, receive, send):
            seen.update(owner=session.session_id(), root=session.root_session_id())
            await send({'type': 'http.response.start', 'status': 200, 'headers': []})
            await send({'type': 'http.response.body', 'body': b''})

        async def send(message): sent.append(message)
        async def receive(): return {'type': 'http.request', 'body': b''}
        scope = {'type': 'http', 'path': '/api/policy', 'scheme': 'https',
                 'headers': [(b'cookie', f'cn_session={root}'.encode())], 'query_string': b'workspace=example'}
        with patch('app.core.session_middleware.resolve_session', return_value=(root, deadline)), \
             patch('app.core.session_middleware.resolve_example_session', return_value=child) as resolve:
            asyncio.run(GuestSessionMiddleware(app)(scope, receive, send))
        self.assertEqual(seen, {'owner': child, 'root': root})
        resolve.assert_called_once_with(root, deadline)
        cookies = [v.decode() for k, v in sent[0]['headers'] if k == b'set-cookie']
        self.assertIn(f'cn_session={root}', cookies[0])
        self.assertNotIn(child, cookies[0])
        with self.assertRaises(RuntimeError): session.session_id()

    def test_personal_workspace_uses_browser_owner_not_example_child(self):
        root = session.new_session_id()
        deadline = datetime.now(timezone.utc) + session.TTL
        seen, sent = {}, []
        async def app(scope, receive, send):
            seen.update(owner=session.session_id(), root=session.root_session_id())
            await send({'type': 'http.response.start', 'status': 200, 'headers': []})
            await send({'type': 'http.response.body', 'body': b''})
        async def send(message): sent.append(message)
        async def receive(): return {'type': 'http.request', 'body': b''}
        scope = {'type': 'http', 'path': '/api/documents', 'scheme': 'https',
                 'headers': [(b'cookie', f'cn_session={root}'.encode())], 'query_string': b'workspace=personal'}
        with patch('app.core.session_middleware.resolve_session', return_value=(root, deadline)), \
             patch('app.core.session_middleware.resolve_example_session', side_effect=AssertionError('Example owner used')):
            asyncio.run(GuestSessionMiddleware(app)(scope, receive, send))
        self.assertEqual(seen, {'owner': root, 'root': root})
        self.assertEqual(sent[0]['status'], 200)

    def test_legacy_demo_name_changes_without_renaming_a_private_policy(self):
        from app.services import policy_store
        for shared in (True, False):
            details = {'members': [{'name': 'Ravi Sharma', 'relation': 'Self', 'age': 32}]}
            doc = {'status': 'ready', 'isDemoTemplate': shared, 'baseFacts': {'planName': 'Example'}}
            with self.subTest(shared=shared), \
                 patch.object(policy_store, '_session_state', return_value={'activePolicyId': 'policy-1', 'policyDetails': details}), \
                 patch.object(policy_store, 'get_policy', return_value=doc), \
                 patch.object(policy_store, 'apply_user_details', side_effect=lambda facts, value: value):
                _, result = policy_store.get_active_policy()
                self.assertEqual(result['facts']['members'][0]['name'], 'Shubham Sharma' if shared else 'Ravi Sharma')
                self.assertEqual(details['members'][0]['name'], 'Ravi Sharma')

    def test_general_conversation_uses_separate_collection_without_document_reads(self):
        database = Mock()
        database.collection.return_value.document.return_value.collection.return_value.document.return_value.get.return_value.exists = False
        token = session.set_session(session.new_session_id())
        self.addCleanup(session.reset_session, token)
        with patch.object(conversation, 'db', return_value=database), \
             patch.object(conversation, 'scope_key', wraps=conversation.scope_key), \
             patch('app.services.case_store.get_case', side_effect=AssertionError('Case read')), \
             patch('app.services.policy_store.get_active_policy_id', side_effect=AssertionError('Policy read')):
            question, context = conversation.prepare('What does a waiting period mean?', 'thread-general-01', general_only=True)
        self.assertEqual(question, 'What does a waiting period mean?')
        self.assertTrue(context['generalOnly'])
        database.collection.return_value.document.return_value.collection.assert_called_once_with('generalThreads')


class Ref:
    def __init__(self, database, path): self.database, self.path = database, path
    def document(self, name): return Ref(self.database, self.path + '/' + name)
    def collection(self, name): return Ref(self.database, self.path + '/' + name)
    def get(self, **kwargs):
        value = deepcopy(self.database.records.get(self.path))
        return SimpleNamespace(exists=value is not None, to_dict=lambda: value)


class Database:
    def __init__(self, records): self.records = records
    def collection(self, name): return Ref(self, name)
    def transaction(self): return self
    def set(self, ref, value, merge=False):
        self.records[ref.path] = {**(self.records.get(ref.path, {}) if merge else {}), **deepcopy(value)}
    def create(self, ref, value):
        if ref.path in self.records: raise AssertionError('Duplicate identity')
        self.set(ref, value)


class ExampleIdentityTests(unittest.TestCase):
    def test_child_is_stable_per_parent_and_cannot_reuse_another_parents_pointer(self):
        from app.services import session_registry
        deadline = datetime.now(timezone.utc) + session.TTL
        a, b = session.new_session_id(), session.new_session_id()
        database = Database({f'guestSessions/{sid}': {'expiresAt': deadline} for sid in (a, b)})
        with patch.object(session_registry, 'db', return_value=database), \
             patch.object(session_registry.firestore, 'transactional', side_effect=lambda fn: fn):
            child_a = session_registry.resolve_example_session(a, deadline)
            self.assertEqual(session_registry.resolve_example_session(a, deadline), child_a)
            database.records[f'guestSessions/{b}']['exampleSessionId'] = child_a
            child_b = session_registry.resolve_example_session(b, deadline)
        self.assertNotEqual(child_a, child_b)
        self.assertEqual(database.records[f'guestSessions/{child_b}']['parentSessionId'], b)

    def test_delete_from_example_context_revokes_the_parent_family(self):
        from fastapi.testclient import TestClient
        from app.main import app
        root, child = session.new_session_id(), session.new_session_id()
        with patch('app.core.session_middleware.resolve_session', return_value=(root, datetime.now(timezone.utc) + session.TTL)), \
             patch('app.core.session_middleware.resolve_example_session', return_value=child), \
             patch('app.routers.session.delete_guest') as delete:
            with TestClient(app) as client:
                result = client.delete('/api/session?workspace=example')
        self.assertEqual(result.status_code, 204)
        delete.assert_called_once_with(root)


class ExampleTemplateTests(unittest.TestCase):
    def setUp(self):
        self.deadline = datetime.now(timezone.utc) + session.TTL
        self.template = {'status': 'ready', 'embeddingModel': 'text-embedding-005', 'policyId': 'demo-known',
                         'case': {'bill': {'total': 246000, 'reviewed': False}, 'documents': [{'id': 'doc-known'}]},
                         'originals': {'doc-known': 'demo/templates/v1/doc-known.pdf'}}
        self.database = Database({'demoTemplates/v1': self.template})
        self.storage = Mock()

    def ensure(self, root, child):
        self.database.records.setdefault('guestSessions/' + child, {'parentSessionId': root, 'expiresAt': self.deadline})
        tokens = session.set_session(child), session.set_root_session(root), session.set_deadline(self.deadline)
        try:
            with patch.object(example_workspace, 'db', return_value=self.database), \
                 patch.object(example_workspace, 'bucket', return_value=self.storage), \
                 patch.object(example_workspace, 'template_version', return_value='v1'), \
                 patch.object(example_workspace, 'get_settings', return_value=SimpleNamespace(embedding_model='text-embedding-005')), \
                 patch.object(example_workspace.policy_store, 'get_policy', return_value={'status': 'ready', 'isDemoTemplate': True}), \
                 patch.object(example_workspace.firestore, 'transactional', side_effect=lambda fn: fn):
                return example_workspace.ensure_example_workspace()
        finally:
            session.reset_deadline(tokens[2]); session.reset_root_session(tokens[1]); session.reset_session(tokens[0])

    def test_two_visitors_get_private_mutable_copies_and_reopen_preserves_edits(self):
        a, b = session.new_session_id(), session.new_session_id()
        self.assertTrue(self.ensure('root-a', a)['ready'])
        self.database.records['cases/' + a]['bill']['total'] = 123
        self.assertTrue(self.ensure('root-b', b)['ready'])
        self.assertEqual(self.database.records['cases/' + b]['bill']['total'], 246000)
        self.assertEqual(self.template['case']['bill']['total'], 246000)
        copies = self.storage.copy_blob.call_count
        self.ensure('root-a', a)
        self.assertEqual(self.storage.copy_blob.call_count, copies)
        self.assertEqual(self.database.records['cases/' + a]['bill']['total'], 123)
        destinations = [c.args[2] for c in self.storage.copy_blob.call_args_list]
        self.assertEqual(destinations, [f'cases/{a}/doc-known.pdf', f'cases/{b}/doc-known.pdf'])

    def test_missing_template_fails_without_reprocessing_documents(self):
        self.database.records.clear()
        with self.assertRaises(example_workspace.ExampleNotPrepared):
            self.ensure('root-a', session.new_session_id())
        self.storage.copy_blob.assert_not_called()

    def test_existing_case_is_not_replaced(self):
        child = session.new_session_id()
        self.database.records['cases/' + child] = {'bill': {'total': 777}}
        with self.assertRaises(ValueError): self.ensure('root-a', child)
        self.assertEqual(self.database.records['cases/' + child]['bill']['total'], 777)


class KotakExampleTests(unittest.TestCase):
    def test_reset_only_deletes_owned_example(self):
        root, child = session.new_session_id(), session.new_session_id()
        database = Database({'guestSessions/' + child: {'parentSessionId': root}})
        tokens = session.set_session(child), session.set_root_session(root)
        try:
            with patch.object(example_workspace, 'db', return_value=database), patch('app.services.data_lifecycle.delete_guest') as delete:
                self.assertTrue(example_workspace.reset_example_workspace()['reset'])
                delete.assert_called_once_with(child)
                database.records['guestSessions/' + child]['parentSessionId'] = 'another-owner'
                with self.assertRaises(ValueError): example_workspace.reset_example_workspace()
                self.assertEqual(delete.call_count, 1)
        finally:
            session.reset_root_session(tokens[1]); session.reset_session(tokens[0])

    def test_fictional_room_selection_preserves_edited_limit(self):
        from app.services.demo_profile import apply_demo_selections
        result = apply_demo_selections({'roomRent': {'amount': 3200}}, ['fictional'])
        self.assertEqual(result['roomRent']['amount'], 3200)
        self.assertIn('3,200', result['roomRent']['label'])

    def test_past_claim_and_originals_are_attached_to_child(self):
        helper = ExampleTemplateTests(); helper.setUp()
        helper.template['pastClaims'] = [{'id': 'older', 'summary': {'claimedAmount': 73420}, 'case': {'documents': [{'id': 'doc-old'}]}}]
        helper.template['originals']['doc-old'] = 'demo/templates/v1/doc-old.pdf'
        child = session.new_session_id()
        helper.ensure('root', child)
        self.assertEqual(helper.database.records[f'cases/{child}/pastClaims/older']['summary']['claimedAmount'], 73420)
        self.assertEqual(helper.storage.copy_blob.call_count, 2)
        self.assertNotIn('cases/root', helper.database.records)
