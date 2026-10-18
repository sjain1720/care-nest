"""Synthetic live follow-up verification with isolated guests and policy switch.

Reads only records belonging to its own test guests; never logs their cookies.
Model answer relevance is recorded for manual review, separate from storage checks.
"""
import argparse
import json
import sys
import time
import uuid
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.core.gcp import db


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('url')
    parser.add_argument('report', type=Path)
    args = parser.parse_args()
    base = args.url.rstrip('/')
    visitors = [requests.Session(), requests.Session()]
    report = {'url': base, 'checks': [], 'answers': []}
    thread = str(uuid.uuid4())

    def call(visitor, method, path, **kwargs):
        response = visitor.request(method, base + path, timeout=300, **kwargs)
        response.raise_for_status()
        return response

    def check(label, condition):
        report['checks'].append({'check': label, 'passed': bool(condition)})
        print(('PASS ' if condition else 'FAIL ') + label, flush=True)
        if not condition:
            raise AssertionError(label)

    def saved(visitor):
        snap = db().collection('conversations').document(visitor.cookies.get('cn_session')).collection('threads').document(thread).get()
        return snap.to_dict() or {}

    def ask(visitor, question):
        started = time.monotonic()
        result = call(visitor, 'POST', '/api/copilot/ask', json={'question': question, 'conversationId': thread}).json()
        report['answers'].append({'question': question, 'elapsedSeconds': round(time.monotonic() - started, 2), 'answer': result['answer']})
        return result['answer']

    try:
        a, b = visitors
        call(a, 'POST', '/api/demo/load')
        call(b, 'GET', '/api/health')
        ask(a, 'Does my policy cover treatment for diabetes?')
        ask(a, 'It was diagnosed on 1 September 2026. There were no earlier symptoms. What should I confirm?')
        original = saved(a)
        check('latest diagnosis clarification retained verbatim', '1 September 2026' in original['turns'][-1]['user'])
        check('history bounded to four turns', 0 < len(original['turns']) <= 4)
        check('another guest cannot inherit same thread history', not saved(b))
        ask(b, 'What was my diagnosis date?')
        check('another guest has only their own question', len(saved(b)['turns']) == 1 and '1 September 2026' not in json.dumps(saved(b)['turns']))
        with (ROOT / 'frontend/public/demo/sample_policy.pdf').open('rb') as policy:
            call(a, 'POST', '/api/documents', files={'file': ('synthetic-followup-policy.pdf', policy, 'application/pdf')}, data={'docType': 'Policy document'})
        ask(a, 'What is my room-rent limit?')
        switched = saved(a)
        check('private policy switch changes conversation scope', switched['scope'] != original['scope'])
        check('policy switch discards prior date clarification', len(switched['turns']) == 1 and '1 September 2026' not in json.dumps(switched['turns']))
        report['storageChecksPassed'] = True
    except Exception as exc:
        report['errorType'] = type(exc).__name__
        report['storageChecksPassed'] = False
    finally:
        for visitor in visitors:
            try:
                call(visitor, 'DELETE', '/api/session')
            except Exception:
                report['checks'].append({'check': 'test guest deletion', 'passed': False})
        report['allChecksPassed'] = report.get('storageChecksPassed', False) and all(item['passed'] for item in report['checks'])
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2))
    return 0 if report['allChecksPassed'] else 1


if __name__ == '__main__':
    sys.exit(main())
