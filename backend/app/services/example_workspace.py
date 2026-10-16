"""Attach only a prepared, versioned synthetic template to an isolated visitor.

Preparing the template is an operator task. Opening a page does not call models,
OCR, or the ingestion pipeline, and cannot overwrite an existing visitor case.
"""
from copy import deepcopy
from functools import lru_cache
from hashlib import sha256
import json

from google.cloud import firestore

from app.core.config import get_settings
from app.core.gcp import bucket, db
from app.core.session import expiry, root_session_id, session_id
from app.services.demo_loader import _demo_dir, _FILES, DEMO_DETAILS
from app.services import policy_store


class ExampleNotPrepared(RuntimeError):
    pass


@lru_cache
def template_version() -> str:
    folder = _demo_dir()
    manifest = [(name, sha256((folder / name).read_bytes()).hexdigest()) for name, _ in _FILES]
    return sha256(json.dumps({'schema': 1, 'files': manifest, 'encoder': get_settings().embedding_model}, sort_keys=True).encode()).hexdigest()[:24]


def ensure_example_workspace() -> dict:
    if root_session_id() == session_id():
        raise ValueError('The example workspace selector is required')
    result = {'ready': True, 'profile': 'Ravi Sharma', 'fictional': True,
              'workspaceKey': sha256(session_id().encode()).hexdigest()[:16]}
    client = db()
    identity = client.collection('guestSessions').document(session_id())
    state = identity.get().to_dict() or {}
    if state.get('examplePrepared'):
        return result
    version = template_version()
    template = client.collection('demoTemplates').document(version).get().to_dict() or {}
    if template.get('status') != 'ready' or template.get('embeddingModel') != get_settings().embedding_model:
        raise ExampleNotPrepared('The example workspace is temporarily unavailable. Please retry shortly.')
    policy_id = template['policyId']
    policy = policy_store.get_policy(policy_id)
    if not policy or policy.get('status') != 'ready' or not policy.get('isDemoTemplate'):
        raise ExampleNotPrepared('The example policy is temporarily unavailable.')
    case = deepcopy(template['case'])
    storage = bucket()
    # Original PDFs are copied into this visitor's private file paths; existing
    # document authorization and deletion behavior therefore remain unchanged.
    for document in case.get('documents', []):
        doc_id = document['id']
        if doc_id not in template['originals']:
            raise ExampleNotPrepared('The example document bundle is incomplete.')
        storage.copy_blob(storage.blob(template['originals'][doc_id]), storage, f'cases/{session_id()}/{doc_id}.pdf')
    case_ref = client.collection('cases').document(session_id())
    session_ref = client.collection('sessions').document(session_id())

    @firestore.transactional
    def attach(transaction):
        identity_snap = identity.get(transaction=transaction)
        current_identity = identity_snap.to_dict() or {}
        existing_case = case_ref.get(transaction=transaction)
        if not identity_snap.exists or current_identity.get('revoked') or current_identity.get('expiresAt') != expiry():
            raise ValueError('This workspace has expired')
        if current_identity.get('examplePrepared'):
            return
        if existing_case.exists:
            raise ValueError('An existing workspace cannot be replaced by the example')
        transaction.set(case_ref, {**case, 'expireAt': expiry(), 'updatedAt': firestore.SERVER_TIMESTAMP})
        transaction.set(session_ref, {'activePolicyId': policy_id, 'policyDetails': deepcopy(DEMO_DETAILS),
                                     'expireAt': expiry(), 'updatedAt': firestore.SERVER_TIMESTAMP})
        transaction.set(identity, {'examplePrepared': version}, merge=True)

    attach(client.transaction())
    return result
