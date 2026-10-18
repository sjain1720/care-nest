"""One-time original-policy / fictional-claims preparation through the real pipeline."""
from hashlib import sha256
from pathlib import Path

from app.services import case_store, policy_store
from app.services.policy_ingest import process_upload, ingest_policy
from app.services.demo_profile import DEMO_DETAILS, DEMO_ASSUMPTIONS, POLICY_SHA256

_APP = Path(__file__).resolve().parents[1]
_DEMO_DIRS = [_APP.parent / 'static' / 'demo', _APP.parents[1] / 'demo-data']
_FILES = (('kotak_group_health_assure.pdf', 'Policy document'), ('previous_bill.pdf', 'Hospital bill'),
          ('previous_settlement.pdf', 'Settlement letter'), ('hospital_bill.pdf', 'Hospital bill'),
          ('settlement_letter.pdf', 'Settlement letter'))
_PUBLIC_FILES = [name for name, _ in _FILES] + ['coverage_assumptions.pdf']


def _demo_dir() -> Path:
    for folder in _DEMO_DIRS:
        if all((folder / name).exists() for name in _PUBLIC_FILES): return folder
    raise FileNotFoundError('Demo bundle missing. Run demo-data/make_kotak_demo.py first.')


def load_demo_case() -> list[dict]:
    """Only exact fixed original wording is shareable. Other documents are synthetic."""
    folder = _demo_dir()
    if sha256((folder / _FILES[0][0]).read_bytes()).hexdigest() != POLICY_SHA256:
        raise ValueError('The allowlisted original Kotak wording changed')
    results = []
    for name, kind in _FILES:
        if name == 'hospital_bill.pdf':
            case_store.add_timeline_event({'id': 'sample-previous-closed', 'kind': 'closed', 'date': '2026-05-12'})
            case_store.start_new_claim()
        data = (folder / name).read_bytes()
        result = ingest_policy(data, name, shared_demo=True) if kind == 'Policy document' else process_upload(data, name, kind)
        if kind == 'Policy document':
            policy_store.save_session_details(DEMO_DETAILS)
            policy_store._save_session_state({'demoAssumptions': DEMO_ASSUMPTIONS})
        if kind == 'Hospital bill':
            header = case_store.get_case().get('billHeader') or {}
            case_store.update_case({'billHeader': {**header, 'title': 'Previous short hospital stay' if name == 'previous_bill.pdf' else "Mother's fracture-repair claim",
                                                   'relation': 'Self' if name == 'previous_bill.pdf' else 'Mother'}})
        print(f'Prepared {name}: {result.pages} pages', flush=True)
        results.append({'file': name, 'type': result.detectedType, 'pages': result.pages, 'reused': result.reused, 'message': result.message})
    return results
