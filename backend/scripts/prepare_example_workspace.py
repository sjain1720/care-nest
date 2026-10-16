"""Prepare the exact public synthetic example once; never run on a visitor page load.

Run from backend: PYTHONPATH=. .venv/bin/python scripts/prepare_example_workspace.py
Uses the real extraction pipeline, publishes only the fixed fixture bundle and
deletes its own temporary guest. It never reads another visitor's documents.
"""
from hashlib import sha256
import json

from app.core.gcp import bucket, db
from app.core.config import get_settings
from app.core.session import set_session, reset_session, set_deadline, reset_deadline
from app.services.session_registry import resolve_session
from app.services.demo_loader import _demo_dir, _FILES, load_demo_case
from app.services.example_workspace import template_version
from app.services import case_store, policy_store
from app.services.data_lifecycle import delete_guest


def main():
    version = template_version()
    ref = db().collection('demoTemplates').document(version)
    if (ref.get().to_dict() or {}).get('status') == 'ready':
        print(json.dumps({'version': version, 'ready': True, 'reused': True}))
        return
    sid, deadline = resolve_session(None)
    token, deadline_token = set_session(sid), set_deadline(deadline)
    try:
        load_demo_case()
        policy = policy_store.get_active_policy()
        if not policy or not policy[1].get('isDemoTemplate'):
            raise RuntimeError('Expected only the canonical fictional policy')
        case = case_store.get_case()
        folder = _demo_dir()
        expected = {'doc-' + sha256((folder / name).read_bytes()).hexdigest()[:16]
                    for name, kind in _FILES if kind != 'Policy document'}
        if {d['id'] for d in case.get('documents', [])} != expected:
            raise RuntimeError('Only the exact fictional bill and settlement may be published')
        originals = {}
        for doc_id in sorted(expected):
            destination = f'demo/templates/{version}/{doc_id}.pdf'
            bucket().copy_blob(bucket().blob(f'cases/{sid}/{doc_id}.pdf'), bucket(), destination)
            originals[doc_id] = destination
        case = {k: v for k, v in case.items() if k not in ('id', 'updatedAt', 'expireAt')}
        ref.set({'status': 'ready', 'schema': 1, 'policyId': policy[0], 'case': case,
                 'embeddingModel': get_settings().embedding_model, 'originals': originals})
        print(json.dumps({'version': version, 'ready': True, 'documents': len(originals),
                          'billRows': len((case.get('bill') or {}).get('items', []))}), flush=True)
    finally:
        try:
            delete_guest(sid)
        finally:
            reset_deadline(deadline_token)
            reset_session(token)


if __name__ == '__main__':
    main()
