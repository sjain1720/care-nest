"""Disposable synthetic ADK review check. Does not print guest identifiers."""
import argparse
import json
import time
from pathlib import Path
import requests


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('url'); p.add_argument('report', type=Path)
    a = p.parse_args(); base = a.url.rstrip('/'); visitor = requests.Session()
    report = {'url': base, 'checks': [], 'started': time.time()}
    def call(method, path, **kwargs):
        response = visitor.request(method, base + path, timeout=300, **kwargs)
        response.raise_for_status(); return response
    def check(name, ok):
        report['checks'].append({'check': name, 'passed': bool(ok)})
        print(('PASS ' if ok else 'FAIL ') + name, flush=True)
        if not ok: raise AssertionError(name)
    try:
        missing = call('POST', '/api/case/dispute/review', json={'question': 'Why was money deducted?'}).json()
        check('empty guest requests documents without running specialists', missing['status'] == 'needs_inputs' and len(missing['steps']) == 1)
        call('POST', '/api/demo/load')
        unreviewed = call('GET', '/api/case/dispute/inputs').json()
        check('unreviewed bill is flagged', any(i['code'] == 'bill_unreviewed' for i in unreviewed['missingInputs']))
        bill = call('GET', '/api/case/bill').json()
        call('PUT', '/api/case/bill', json={'items': bill['items'], 'statedTotal': bill['total']})
        inputs = call('GET', '/api/case/dispute/inputs').json()
        check('reviewed linked inputs ready', inputs['status'] == 'ready_for_review')
        started = time.monotonic()
        response = call('POST', '/api/case/dispute/review/stream', json={'question': 'Explain each deduction and the missing facts without promising payment.'})
        events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
        review = next(e['review'] for e in events if e['type'] == 'review')
        report['elapsedSeconds'] = round(time.monotonic() - started, 2); report['review'] = review
        check('ADK review completes', review['status'] == 'reviewed' and review['engine'] == 'adk_investigation')
        names = {s['agent'] for s in review['steps']}
        check('shared support and source verifier report progress', {'Shared Verifier', 'Source Verifier'} <= names)
        check('adaptive policy retrieval ran', any('Retrieved policy evidence' in step['label'] for step in review['steps']))
        check('every extracted deduction is represented', len(review['rows']) == len(call('GET', '/api/case/settlement').json()['deductions']))
        check('no-reason deduction is not inferred', any(r['assessment'] == 'no_stated_reason' and not r['citations'] for r in review['rows']))
        check('review contains actionable missing-fact questions', all(r['missingInformation'] for r in review['rows']))
        report['allPassed'] = True
    except Exception as exc:
        report['allPassed'] = False; report['errorType'] = type(exc).__name__
    finally:
        try: call('DELETE', '/api/session')
        except Exception: report['allPassed'] = False; report['cleanupFailed'] = True
        a.report.parent.mkdir(parents=True, exist_ok=True); a.report.write_text(json.dumps(report, indent=2))
    return 0 if report['allPassed'] else 1
if __name__ == '__main__': raise SystemExit(main())
