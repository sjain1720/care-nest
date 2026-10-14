"""One synthetic normal-chat investigation, editable letter and follow-up release gate."""
import argparse
import json
from pathlib import Path
import requests


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('url'); parser.add_argument('report', type=Path)
    args = parser.parse_args(); visitor = requests.Session(); peer = requests.Session()
    report = {'checks': [], 'allPassed': False}; thread = 'synthetic-claim-journey'
    def call(method, path, **kwargs):
        response = visitor.request(method, args.url.rstrip('/') + path, timeout=300, **kwargs)
        response.raise_for_status(); return response
    def check(name, condition):
        report['checks'].append({'check': name, 'passed': bool(condition)})
        print(('PASS ' if condition else 'FAIL ') + name, flush=True)
        if not condition: raise AssertionError(name)
    try:
        missing = call('POST', '/api/copilot/ask', json={'question': 'Investigate my settlement deductions.', 'conversationId': thread}).json()['answer']
        check('normal chat requests missing inputs', missing['investigation']['status'] == 'needs_inputs')
        call('POST', '/api/demo/load')
        bill = call('GET', '/api/case/bill').json()
        call('PUT', '/api/case/bill', json={'items': bill['items'], 'statedTotal': bill['total']})
        stream = call('POST', '/api/copilot/ask/stream', json={'conversationId': thread,
            'question': 'Why was money deducted from my claim? Investigate policy, bill and settlement and prepare a clarification letter.'})
        events = [json.loads(line[6:]) for line in stream.text.splitlines() if line.startswith('data: ')]
        answer = next(e['answer'] for e in events if e['type'] == 'answer')
        report.update(answer=answer, steps=[e['step'] for e in events if e['type'] == 'step'])
        review = answer['investigation']
        check('normal SSE returns an adaptive verified result', review['engine'] == 'adk_investigation' and review['status'] == 'reviewed')
        check('actual scoped retrieval ran', any('Retrieved policy evidence' in s['label'] for s in report['steps']))
        check('shared backend verifier ran', any(s['agent'] == 'Shared Verifier' for s in report['steps']))
        check('at least one policy interpretation is supported and cited', any(r['assessment'] == 'related_wording' and r['citations'] for r in review['rows']))
        check('unknown reason is not inferred', any(r['assessment'] == 'no_stated_reason' and not r['citations'] for r in review['rows']))
        check('questions identify who supplies evidence', bool(review['actions']) and all(a['source'] and a['question'] for a in review['actions']))
        check('calls bounded including child agents and support review', review['metrics']['modelCalls'] <= 9 and review['metrics']['toolCalls'] <= 10)
        letter = call('GET', '/api/case/letter?kind=clarification').json(); report['letter'] = letter
        check('letter uses investigation questions', all(a['question'] in letter['body'] for a in review['actions']))
        check('draft has an evidence index', bool(letter['evidenceIndex']))
        followup = call('POST', '/api/copilot/ask', json={'conversationId': thread,
            'question': 'Explain the room-rent policy clause you cited.'}).json()['answer']; report['followup'] = followup
        check('simple follow-up returns to Python', followup.get('investigation') is None)
        check('follow-up retains sourced policy context', bool(followup['citations']))
        other = peer.post(args.url.rstrip('/') + '/api/copilot/ask', json={'conversationId': thread,
            'question': 'Investigate my settlement deductions.'}, timeout=60)
        other.raise_for_status()
        check('same thread id in another guest cannot reuse findings', other.json()['answer']['investigation']['status'] == 'needs_inputs')
        report['allPassed'] = True
    except Exception as exc:
        report['errorType'] = type(exc).__name__
    finally:
        for client in (visitor, peer):
            try: client.delete(args.url.rstrip('/') + '/api/session', timeout=60).raise_for_status()
            except Exception: report.update(allPassed=False, cleanupFailed=True)
        args.report.parent.mkdir(parents=True, exist_ok=True); args.report.write_text(json.dumps(report, indent=2))
    return 0 if report['allPassed'] else 1


if __name__ == '__main__': raise SystemExit(main())
