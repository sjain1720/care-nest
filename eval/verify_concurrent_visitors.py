"""One bounded three-visitor SSE exercise; no uploads, retries or existing guest changes.

Uses real cloud-backed prepared examples through a chosen local/hosted API.
This is prepared-example concurrency evidence, not ingestion capacity or a load benchmark.
"""
import ast
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import http.cookiejar
import json
import os
import subprocess
from pathlib import Path
import threading
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get('CARENEST_BASE_URL', 'http://127.0.0.1:8088').rstrip('/')
OUT = ROOT / 'eval/results/concurrent-visitors' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
QUESTIONS = ['What is my room-rent limit?', 'How much coverage is remaining?',
             'Why was ₹20,000 deducted from my current claim? Examine each reason against my policy and tell me what evidence is missing.']


class Visitor:
    def __init__(self, index):
        self.index = index
        self.client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.created = False

    def call(self, path, method='GET', data=None):
        request = urllib.request.Request(BASE + path, method=method,
            data=json.dumps(data).encode() if data is not None else None,
            headers={'Content-Type': 'application/json'})
        with self.client.open(request, timeout=80) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else None

    def prepare(self):
        self.call('/api/session/profile?workspace=general')
        self.created = True
        self.call('/api/session/profile?workspace=general', 'PUT', {'displayName': f'Concurrent tester {self.index}'})
        started = time.monotonic()
        self.call('/api/demo/ensure?workspace=example', 'POST', {})
        return round(time.monotonic() - started, 3)

    def ask(self, barrier):
        result = {'visitor': self.index, 'question': QUESTIONS[self.index - 1]}
        barrier.wait(timeout=10)
        started = time.monotonic()
        result['startedUtc'] = datetime.now(timezone.utc).isoformat()
        answer = None
        try:
            request = urllib.request.Request(BASE + '/api/copilot/ask/stream?workspace=example', method='POST',
                data=json.dumps({'question': result['question']}).encode(), headers={'Content-Type': 'application/json'})
            with self.client.open(request, timeout=260) as response:
                result['httpStatus'] = response.status
                for line in response:
                    if not line.startswith(b'data:'):
                        continue
                    event = json.loads(line[5:].strip())
                    if event.get('type') == 'step' and 'firstProgressSeconds' not in result:
                        result['firstProgressSeconds'] = round(time.monotonic() - started, 3)
                    if event.get('type') == 'answer':
                        answer = event['answer']
                    if event.get('type') == 'error':
                        result['streamError'] = event.get('message')
            result['answerReceived'] = bool(answer)
            if answer:
                result['verdict'] = answer['verdict']
                if self.index == 1:
                    result['expectedOutcome'] = '2,500' in answer['summary'] and 'fictional' in answer['summary'].lower()
                elif self.index == 2:
                    result['expectedOutcome'] = '7,61,580' in (answer['summary'] + answer['headline'])
                else:
                    review = answer.get('investigation') or {}
                    rows = review.get('rows', [])
                    result['expectedOutcome'] = (review.get('status') == 'reviewed'
                        and sorted(r['amount'] for r in rows) == [4800, 6100, 9100]
                        and next(r for r in rows if r['amount'] == 4800)['assessment'] == 'no_stated_reason')
                    result['investigationMetrics'] = review.get('metrics')
                    result['implantTracePresent'] = any(r.get('evidence', {}).get('status') == 'reconciles'
                        for r in rows if r.get('evidence'))
                (OUT / f'answer-{self.index}.json').write_text(json.dumps(answer, indent=2))
        except Exception as error:
            result['errorType'] = type(error).__name__
            if isinstance(error, urllib.error.HTTPError):
                result['httpStatus'] = error.code
        result['completionSeconds'] = round(time.monotonic() - started, 3)
        return result


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    visitors = [Visitor(i) for i in range(1, 4)]
    report = {'base': BASE, 'scope': 'Three real prepared-example requests; no cold uploads, retry loop or user acceptance claim.',
        'commit': subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT, text=True).strip(),
        'results': [], 'checks': [], 'cleanup': []}
    try:
        report['attachmentSeconds'] = [v.prepare() for v in visitors]
        # Review only our exact authored fixture in visitor 3; never a real visitor's bill.
        _, bill = visitors[2].call('/api/case/bill?workspace=example')
        tree = ast.parse((ROOT / 'demo-data/make_kotak_demo.py').read_text())
        rows = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == 'ROWS' for t in n.targets))
        assert bill['total'] == 185000 and len(bill['items']) == len(rows) == 15
        assert sorted(i['amount'] for i in bill['items']) == sorted(rate * qty for _, _, rate, qty in rows)
        reviewed = [{'description': label, 'category': category, 'rate': rate, 'qty': qty,
                     'amount': rate * qty, 'page': i // 5 + 1} for i, (label, category, rate, qty) in enumerate(rows)]
        visitors[2].call('/api/case/bill?workspace=example', 'PUT', {'items': reviewed, 'statedTotal': 185000})
        barrier = threading.Barrier(3)
        with ThreadPoolExecutor(max_workers=3) as pool:
            report['results'] = list(pool.map(lambda v: v.ask(barrier), visitors))
        for v in visitors:
            _, profile = v.call('/api/session/profile?workspace=general')
            report['checks'].append({'visitor': v.index, 'ownDisplayName': profile.get('displayName') == f'Concurrent tester {v.index}'})
            try:
                code, _ = v.call('/api/policy?workspace=personal')
            except urllib.error.HTTPError as error:
                code = error.code
            report['checks'][-1]['personalPolicyStillEmpty'] = code == 404
        report['passed'] = all(r.get('answerReceived') and r.get('expectedOutcome') and not r.get('streamError')
            for r in report['results']) and all(c['ownDisplayName'] and c['personalPolicyStillEmpty'] for c in report['checks'])
    except Exception as error:
        report.update(passed=False, errorType=type(error).__name__)
    finally:
        for v in visitors:
            if v.created:
                try:
                    code, _ = v.call('/api/session?workspace=general', 'DELETE')
                except Exception:
                    code = 'failed'
                report['cleanup'].append({'visitor': v.index, 'status': code})
        report['passed'] = report.get('passed', False) and all(c['status'] == 204 for c in report['cleanup'])
        (OUT / 'report.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report, ensure_ascii=False), flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
