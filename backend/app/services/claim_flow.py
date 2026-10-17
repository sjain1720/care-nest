"""Owned document tasks and deterministic responses to an insurer's paper request."""
import hashlib
import json
import secrets
from datetime import datetime, timezone

from app.services import case_store, policy_store
from app.services.case_builder import build_case
from app.services.letters import template_body, letter_facts


class FlowConflict(ValueError):
    pass


def ensure_context():
    def initialize(case):
        return {} if case.get('flowId') else {'flowId': secrets.token_hex(16)}
    return case_store.mutate_case(initialize)['flowId']


def latest_reply(case):
    replies = [e for e in case.get('timeline', []) if e.get('kind') == 'reply']
    return sorted(replies, key=lambda e: e.get('date', ''))[-1] if replies else None


def task_list(case):
    tasks = []
    for item in build_case(case)['checklist']:
        tasks.append({'id': 'check-' + item['id'], 'label': item['name'], 'kind': 'checklist',
                      'checklistId': item['id'], 'replyId': None, 'source':item['source'], 'why':item['why'], 'checklistStatus':item['status'], 'basis': 'General checklist; confirm insurer requirements'})
    reply = latest_reply(case)
    if reply and reply.get('outcome') == 'asks_for_papers':
        for index, text in enumerate(reply.get('papersAsked', [])[:30]):
            digest = hashlib.sha256(str(text).encode()).hexdigest()[:12]
            tasks.append({'id': f"reply-{reply['id']}-{index}-{digest}", 'label': str(text)[:500],
                          'kind': 'reply', 'checklistId': None, 'replyId': reply['id'],
                          'source':'Insurer / TPA reply', 'why':'Respond to this stated request; ask for clarification if it is unclear.', 'checklistStatus':None, 'basis': 'Extracted insurer request; review against the original reply'})
    documents = {d['id']: d for d in case.get('documents', [])}
    states = case.get('documentTaskStates') or {}
    for task in tasks:
        saved = states.get(task['id']) or {}
        linked = [documents[i] for i in saved.get('documentIds', []) if i in documents]
        task.update(documents=linked, reviewed=bool(saved.get('reviewed') and linked), note=saved.get('note', ''),
                    notApplicable=bool(saved.get('notApplicable') and saved.get('note')))
    return tasks


def view(case):
    tasks = task_list(case)
    fingerprint = hashlib.sha256(json.dumps({'flowId': case.get('flowId'), 'tasks': tasks,
        'reply': latest_reply(case), 'policyId': case.get('policyId')}, sort_keys=True, default=str).encode()).hexdigest()
    return {'claimKey': case['flowId'], 'fingerprint': fingerprint, 'tasks': tasks,
            'replyId': (latest_reply(case) or {}).get('id')}


def current_tasks():
    ensure_context()
    return view(case_store.get_case())


def update_task(task_id, body):
    def change(case):
        if case.get('flowId') != body.claimKey:
            raise FlowConflict('The selected claim changed. Return to its documents before continuing.')
        if body.expectedFingerprint and body.expectedFingerprint != view(case)['fingerprint']:
            raise FlowConflict('These document tasks changed in another request. Refresh before saving your review.')
        tasks = {t['id']: t for t in task_list(case)}
        if task_id not in tasks:
            raise FlowConflict('This checklist or insurer request changed. Refresh the documents page.')
        owned = {d['id'] for d in case.get('documents', [])}
        if any(identity not in owned for identity in body.documentIds):
            raise FlowConflict('A selected file is not part of this claim.')
        if body.reviewed and not body.documentIds:
            raise FlowConflict('Link a document before confirming its review.')
        if body.notApplicable and not body.note.strip():
            raise FlowConflict('Explain why this requested item is not applicable.')
        states = dict(case.get('documentTaskStates') or {})
        states[task_id] = {'documentIds': body.documentIds, 'reviewed': body.reviewed,
                           'notApplicable': body.notApplicable, 'note': body.note.strip()}
        return {'documentTaskStates': states}
    return view(case_store.mutate_case(change))


def link_uploaded(task_id, claim_key, document_id):
    # Preserve concurrent links atomically; uploading never confirms human review.
    def link(case):
        if case.get('flowId') != claim_key:
            raise FlowConflict('The selected claim changed during upload.')
        if task_id not in {t['id'] for t in task_list(case)}:
            raise FlowConflict('The request changed; the file is saved but was not linked. Review your documents.')
        if document_id not in {d['id'] for d in case.get('documents', [])}:
            raise FlowConflict('The uploaded file is not in this claim.')
        states = dict(case.get('documentTaskStates') or {})
        previous = states.get(task_id) or {}
        states[task_id] = {**previous, 'documentIds':list(dict.fromkeys(previous.get('documentIds', []) + [document_id])),
                           'reviewed':False, 'notApplicable':False}
        return {'documentTaskStates':states}
    return view(case_store.mutate_case(link))


def response_fingerprint(case, facts):
    return hashlib.sha256((view(case)['fingerprint'] + json.dumps(facts, sort_keys=True, default=str)).encode()).hexdigest()


def response_draft():
    ensure_context()
    case = case_store.get_case()
    reply = latest_reply(case)
    if not reply or reply.get('outcome') != 'asks_for_papers':
        raise FlowConflict('No current request for papers is recorded. Add or review the insurer reply first.')
    tasks = [t for t in task_list(case) if t['kind'] == 'reply']
    active = policy_store.get_active_policy()
    facts = letter_facts('cover_letter', {**build_case(case), 'bill': case.get('bill')}, active[1]['facts'] if active else {})
    provided, pending, inapplicable = [], [], []
    for task in tasks:
        if task['notApplicable']:
            inapplicable.append(task['label'] + ': ' + task['note'])
        elif task['reviewed']:
            provided.append(task['label'] + ' — ' + ', '.join(d.get('name', 'document') for d in task['documents']))
        else:
            pending.append(task['label'])
    ref = reply.get('reference') or '[insurer reply reference]'
    points = [f"I am responding to your reply dated {reply.get('date', '[reply date]')} (reference {ref})."]
    if provided:
        points.append('I have checked the following documents and will attach the relevant copies when sending this response: ' + '; '.join(provided) + '.')
    if pending:
        points.append('The following requested items are still pending or have not been checked: ' + '; '.join(pending) + '.')
    if inapplicable:
        points.append('My explanation for items marked not applicable: ' + '; '.join(inapplicable) + '.')
    if not tasks:
        points.append('Please confirm the specific documents required; I could not identify a reliable itemized list from your reply.')
    points.append('Please confirm receipt of the documents I send and let me know if any further information is needed.')
    facts.update(points=points, subject='Response to requested documents – Claim ' + (build_case(case).get('claimNumber') or '[claim number]'))
    body = template_body(facts).replace('The documents listed in the evidence index are attached.',
                                      'I will attach the relevant copies when sending this response.')
    return {'kind': 'document_response', 'to': facts['to'], 'subject': facts['subject'], 'body': body,
            'evidenceIndex': provided, 'inputFingerprint': response_fingerprint(case, active[1]['facts'] if active else {}), 'claimKey': case['flowId'], 'replyId': reply['id'],
            'warnings': ['Review the insurer request and fill placeholders. Files are not attached or sent by CareNest.'] +
                        ([f'{len(pending)} requested item(s) are still pending or unchecked. You may edit this draft now.'] if pending or not tasks else [])}
