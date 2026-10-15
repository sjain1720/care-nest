"""Focused real OCR gate: reject blank image, keep readable extraction and cache reuse."""
import argparse
import json
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('url'); parser.add_argument('report', type=Path)
    args = parser.parse_args(); client = requests.Session(); base = args.url.rstrip('/')
    report = {'checks': [], 'allPassed': False}
    def check(name, ok):
        report['checks'].append({'check': name, 'passed': bool(ok)})
        print(('PASS ' if ok else 'FAIL ') + name, flush=True)
        if not ok: raise AssertionError(name)
    def upload(name):
        with (ROOT/'eval/results/fixtures'/name).open('rb') as source:
            return client.post(base+'/api/documents', files={'file':(name,source,'image/png')},
                               data={'docType':'Hospital bill'},timeout=120)
    try:
        blank = upload('blank-bill.png')
        check('blank financial image rejected as unreadable', blank.status_code == 422)
        check('blank image creates no bill', client.get(base+'/api/case/bill',timeout=30).status_code == 404)
        valid = upload('synthetic-bill-page1.png'); valid.raise_for_status()
        response = client.get(base+'/api/case/bill',timeout=30); response.raise_for_status()
        bill = response.json(); report['bill'] = bill
        check('readable image retains actual visible amounts', sum(row['amount'] for row in bill['items']) == 38800 and len(bill['items']) == 2)
        check('partial image reports missing pages', bool(bill['missingPages']))
        check('extraction still requires human review', bill['reviewed'] is False)
        repeated = upload('synthetic-bill-page1.png'); repeated.raise_for_status()
        check('validated image reuses prior result', repeated.json()['reused'] is True)
        report['allPassed'] = True
    except Exception as exc: report['errorType'] = type(exc).__name__
    finally:
        try: client.delete(base+'/api/session',timeout=60).raise_for_status()
        except Exception: report.update(allPassed=False,cleanupFailed=True)
        args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,indent=2))
    return 0 if report['allPassed'] else 1


if __name__=='__main__': raise SystemExit(main())
