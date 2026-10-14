"""One disposable synthetic run of the integrated bounded ADK investigation.

Checks runtime tools and limits; full semantic quality still needs human review.
"""
import argparse
import json
import time
from pathlib import Path
import requests


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('url')
    parser.add_argument('report', type=Path)
    args = parser.parse_args()
    visitor = requests.Session()
    report = {'checks': [], 'allPassed': False}

    def call(method, path, **kwargs):
        response = visitor.request(method, args.url.rstrip('/') + path, timeout=240, **kwargs)
        response.raise_for_status()
        return response.json() if response.content else None

    def check(name, ok):
        report['checks'].append({'check': name, 'passed': bool(ok)})
        print(('PASS ' if ok else 'FAIL ') + name, flush=True)
        if not ok:
            raise AssertionError(name)

    try:
        call('POST', '/api/demo/load')
        bill = call('GET', '/api/case/bill')
        call('PUT', '/api/case/bill', json={'items': bill['items'], 'statedTotal': bill['total']})
        start = time.monotonic()
        response = call('POST', '/api/copilot/ask', json={
            'conversationId': 'synthetic-adk-check',
            'question': 'Investigate my settlement deductions. Inspect the bill and settlement, retrieve relevant policy clauses and identify missing facts. Do not promise payment.'})
        result = response['answer']['investigation']
        report.update(result=result, elapsedSeconds=round(time.monotonic() - start, 2))
        check('normal chat returns the shared verified investigation', result['status'] == 'reviewed')
        labels = [step['label'] for step in result['steps']]
        check('actual runtime consults a specialist', any('Executing tool' in label for label in labels))
        check('actual runtime retrieves policy evidence', any('Retrieved policy evidence' in label for label in labels))
        check('tool budget respected', 0 < result['metrics']['toolCalls'] <= 10)
        check('model calls bounded including child agents and verifier', 0 < result['metrics']['modelCalls'] <= 9)
        check('token usage is measured', result['metrics']['totalTokens'] > 0)
        report['allPassed'] = True
    except Exception as exc:
        report['errorType'] = type(exc).__name__
    finally:
        try:
            call('DELETE', '/api/session')
        except Exception:
            report['allPassed'] = False
            report['cleanupFailed'] = True
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2))
    return 0 if report['allPassed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
