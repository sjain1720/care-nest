"""Prepare fixed original Kotak wording and two fictional claims; never on page load."""
from hashlib import sha256
import json
from io import BytesIO
from pypdf import PdfReader
from app.core.gcp import bucket, db
from app.core.config import get_settings
from app.core.session import set_session, reset_session, set_deadline, reset_deadline
from app.services.session_registry import resolve_session
from app.services.demo_loader import _demo_dir, _FILES, load_demo_case
from app.services.demo_profile import POLICY_SHA256
from app.services.example_workspace import template_version
from app.services import case_store, policy_store
from app.services.data_lifecycle import delete_guest
from app.services.grounding import quote_in_text
from app.services.claim_history import summarize_case
from app.schemas import PolicyFacts


def verified_watchouts(policy_id):
    pages = policy_store.load_pages(policy_id)
    entries = [
        ('Which room-rent option is selected?', 'The wording offers caps with and without proportionate deductions. The issued schedule determines the option. This fictional example selects benefit 13.', 17, 'Benefits 13 and 14', 'Room Rent Capping without proportionate deduction'),
        ('Implants are an important exception', 'Medicines, consumables, implants and diagnostics are treated differently. Ask the insurer to justify a room-ratio cut applied to implant costs.', 17, 'Benefit 13 - exceptions', 'medical implants and diagnostic costs will be reimbursed based on the actual amounts incurred'),
        ('Check differential billing and ICU exceptions', 'Check whether the hospital uses differential billing. The wording excludes ICU charges from proportionate deductions.', 17, 'Benefit 13 - conditions', 'proportionate deductions will not be applied in respect of ICU Charges'),
        ('Co-pay and deductible depend on selections', 'These are schedule-dependent options. Do not assume a co-pay just because someone is over 60. Neither optional co-pay nor deductible is selected in this fictional story.', 18, 'Benefits 15 and 16', 'If the Co-payment is in force'),
        ('Use the actual non-medical list', 'Check the named items in Annexure III List I. A category such as consumables does not by itself establish that every charge is excluded.', 22, 'Exclusion gg', 'All non-medical expenses listed in Annexure III (List I) of the Policy'),
    ]
    traps = []
    for title, explanation, page, clause, quote in entries:
        if not quote_in_text(quote, pages.get(page, '')):
            raise RuntimeError(f'Unverified watch-out quote on page {page}')
        traps.append({'title': title, 'explanation': explanation, 'trust': 'supported', 'citation': {'page': page, 'clause': clause, 'quote': quote}})
    record = policy_store.get_policy(policy_id)
    facts = {**record['baseFacts'], 'traps': traps}
    PolicyFacts.model_validate(facts)
    policy_store.save_policy(policy_id, {'baseFacts': facts, 'facts': facts})
    return traps


def main():
    version = template_version()
    ref = db().collection('demoTemplates').document(version)
    if (ref.get().to_dict() or {}).get('status') == 'ready':
        print(json.dumps({'version': version, 'ready': True, 'reused': True})); return
    sid, deadline = resolve_session(None)
    token, deadline_token = set_session(sid), set_deadline(deadline)
    try:
        folder = _demo_dir()
        if sha256((folder / _FILES[0][0]).read_bytes()).hexdigest() != POLICY_SHA256:
            raise RuntimeError('Only the exact original Kotak PDF may be published')
        # This fixed public original is text-readable. Preserve actual PDF page numbers
        # and checkpoint complete pages so ingestion can index without redundant OCR.
        source = (folder / _FILES[0][0]).read_bytes()
        policy_id = 'demo-' + POLICY_SHA256[:16]
        record = policy_store.get_policy(policy_id) or {}
        if record.get('status') != 'ready':
            pages = [{'page': i + 1, 'text': page.extract_text() or ''} for i, page in enumerate(PdfReader(BytesIO(source)).pages)]
            if len(pages) != 43 or any(len(page['text'].strip()) < 100 for page in pages):
                raise RuntimeError('Expected all 43 readable original policy pages')
            policy_store.save_original(policy_id, source)
            policy_store.save_pages(policy_id, pages)
            policy_store.save_policy(policy_id, {'status': 'processing', 'pageCount': len(pages), 'filename': _FILES[0][0], 'isDemoTemplate': True, 'ownerSessionId': None, 'expireAt': None})
        print('Preparing original Kotak wording and two fictional claims...', flush=True)
        load_demo_case()
        policy = policy_store.get_active_policy()
        if not policy or not policy[1].get('isDemoTemplate'): raise RuntimeError('Expected an allowlisted demo policy')
        traps = verified_watchouts(policy[0])
        case = case_store.get_case()
        archived = list(db().collection('cases').document(sid).collection('pastClaims').stream())
        if len(archived) != 1: raise RuntimeError('Expected exactly one previous claim')
        previous = archived[0].to_dict()['case']
        previous_id = 'cl-20260508'
        past = [{'id': previous_id, 'summary': summarize_case(previous, previous_id), 'case': previous}]
        expected = {'doc-' + sha256((folder / name).read_bytes()).hexdigest()[:16] for name, kind in _FILES if kind != 'Policy document'}
        if {d['id'] for d in case.get('documents', []) + previous.get('documents', [])} != expected:
            raise RuntimeError('Only the four exact fictional files may be published')
        if case['bill']['total'] != 185000 or previous['bill']['total'] != 73420:
            raise RuntimeError(f"Extracted bill totals need review: current={case['bill']['total']}, previous={previous['bill']['total']}")
        if case['settlement']['approvedAmount'] != 165000 or previous['settlement']['approvedAmount'] != 73420:
            raise RuntimeError('Extracted decisions differ from the documents')
        for value in (case, previous):
            if any(c['kind'] in ('missing_pages', 'total_mismatch', 'line_arithmetic') for c in value['bill'].get('checks', [])):
                raise RuntimeError('Review bill arithmetic/pages before publishing')
        originals = {}
        for doc_id in sorted(expected):
            destination = f'demo/templates/{version}/{doc_id}.pdf'
            bucket().copy_blob(bucket().blob(f'cases/{sid}/{doc_id}.pdf'), bucket(), destination)
            originals[doc_id] = destination
        case = {k: v for k, v in case.items() if k not in ('id', 'updatedAt', 'expireAt')}
        ref.set({'status': 'ready', 'schema': 2, 'policyId': policy[0], 'case': case, 'pastClaims': past, 'embeddingModel': get_settings().embedding_model, 'originals': originals})
        print(json.dumps({'version': version, 'ready': True, 'claims': 2, 'documents': len(originals), 'billRows': len(case['bill']['items']), 'watchouts': len(traps)}), flush=True)
    finally:
        try: delete_guest(sid)
        finally: reset_deadline(deadline_token); reset_session(token)


if __name__ == '__main__': main()
