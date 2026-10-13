#!/usr/bin/env python3
"""Repeatable synthetic live release check; never logs cookies or bearer IDs.

Run with backend/.venv/bin/python. --full invokes bill extraction, QA and drafting
and therefore uses Google AI quota. It creates and deletes only its own guests.
"""
import argparse
import json
from pathlib import Path
import sys

import requests

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--full', action='store_true')
    parser.add_argument('--bill-image', type=Path, help='Synthetic bill PNG/JPEG with total 17250')
    parser.add_argument('--output', type=Path, default=ROOT / 'eval/results/release-check.json')
    args = parser.parse_args()
    base = args.url.rstrip('/')
    a, b = requests.Session(), requests.Session()
    results = []

    def check(name, condition):
        results.append({'check': name, 'passed': bool(condition)})
        print(('PASS ' if condition else 'FAIL ') + name, flush=True)
        if not condition:
            raise AssertionError(name)

    def request(client, method, path, expected=200, **kwargs):
        response = client.request(method, base + path, timeout=300, **kwargs)
        check(method + ' ' + path.split('?')[0], response.status_code == expected)
        return response

    try:
        for visitor in (a, b):
            request(visitor, 'GET', '/api/health')
        check('separate guest identities', a.cookies.get('cn_session') != b.cookies.get('cn_session'))
        request(b, 'GET', '/api/policy', expected=404)
        answer = request(b, 'POST', '/api/copilot/ask', json={'question': 'What is a waiting period?'}).json()['answer']
        check('general answer without policy', answer['general'] and answer['verdict'] == 'info')
        personal = request(b, 'POST', '/api/copilot/ask', json={'question': 'Does my policy cover maternity?'}).json()['answer']
        check('personal policy is required', personal['verdict'] == 'cant_confirm' and not personal['citations'])
        if args.full:
            request(a, 'POST', '/api/demo/load')
            check('fictional live context identified', request(a, 'GET', '/api/session').json()['mode'] == 'live_demo')
            request(b, 'GET', '/api/policy', expected=404)
            room = request(a, 'POST', '/api/copilot/ask', json={'question': 'What is my room-rent limit?'}).json()['answer']
            check('policy answer has source page', bool(room['citations']) and any(c['page'] == 7 for c in room['citations']))
            if args.bill_image:
                with args.bill_image.open('rb') as source:
                    request(a, 'POST', '/api/documents', files={'file': ('synthetic-release-bill.png', source, 'image/png')}, data={'docType': 'Hospital bill'})
                extracted = request(a, 'GET', '/api/case/bill').json()
                check('new image total extracted', extracted['total'] == 17250)
                reviewed = request(a, 'PUT', '/api/case/bill', json={
                    'statedTotal': 17250, 'items': extracted['items']}).json()
                check('review recomputes bill', reviewed['reviewed'] and reviewed['total'] == 17250)
            letter = request(a, 'GET', '/api/case/letter?kind=cover_letter').json()
            check('editable draft produced', bool(letter['body']) and bool(letter['evidenceIndex']))
            claim = request(a, 'GET', '/api/case').json()
            doc = claim['documents'][0]['id']
            request(b, 'GET', '/api/case/document/' + doc, expected=404)
            # Private policy upload is isolated even when the bytes match.
            with (ROOT / 'frontend/public/demo/sample_policy.pdf').open('rb') as source:
                request(a, 'POST', '/api/documents', files={'file': ('synthetic-private-policy.pdf', source, 'application/pdf')}, data={'docType': 'Policy document'})
            check('personal upload exits demo context', request(a, 'GET', '/api/session').json()['mode'] == 'guest')
            request(b, 'GET', '/api/policy', expected=404)
        promise = request(a, 'POST', '/api/copilot/ask/stream', json={'question': 'Will my claim definitely be approved?'}).text
        check('streaming refuses approval guarantee', 'cant_confirm' in promise and '"type": "error"' not in promise)
    except Exception as exc:
        results.append({'check': 'release flow completed', 'passed': False, 'errorType': type(exc).__name__})
        print(type(exc).__name__ + ': release check stopped', file=sys.stderr)
    finally:
        for visitor in (a, b):
            try:
                request(visitor, 'DELETE', '/api/session', expected=204)
                request(visitor, 'GET', '/api/policy', expected=404)
            except Exception:
                results.append({'check': 'test guest cleanup', 'passed': False})
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps({'results': results, 'allPassed': all(r['passed'] for r in results)}, indent=2))
    return 0 if all(r['passed'] for r in results) else 1


if __name__ == '__main__':
    sys.exit(main())
