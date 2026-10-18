"""Capture one real candidate investigation for joint human review; synthetic owned visitor only."""
import ast
import os
import json
import time
import shutil
from datetime import datetime, timezone
import urllib.request
import urllib.error
import http.cookiejar
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'eval/results/j0-review/local'
OUT.mkdir(parents=True,exist_ok=True)
ONLY_BILL = os.environ.get('CARENEST_REVIEW_ONLY_BILL') == '1'
TARGET = OUT / ('bill-evidence.json' if ONLY_BILL else 'capture.json')
if (OUT/'capture.json').exists():
    shutil.copy2(OUT/'capture.json', OUT/('capture-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.json'))
BASE='http://127.0.0.1:8088'
client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
report={'base':BASE,'mode':'actual AI investigation/follow-ups on prepared synthetic documents; source-based bill review; human acceptance pending','turns':[]}
def call(path,method='GET',body=None,timeout=260):
    started=time.monotonic()
    req=urllib.request.Request(BASE+path,method=method,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'})
    with client.open(req,timeout=timeout) as response:
        value=response.read()
        return (json.loads(value) if value else None),round(time.monotonic()-started,3)
def save(): TARGET.write_text(json.dumps(report,indent=2))
try:
    call('/api/session/profile?workspace=general')
    call('/api/session/profile?workspace=general','PUT',{'displayName':'Joint review'})
    call('/api/demo/ensure?workspace=example','POST',{})
    bill,_=call('/api/case/bill?workspace=example')
    # This only reviews our exact authored fictional fixture; never modify a real visitor's bill.
    tree=ast.parse((ROOT/'demo-data/make_kotak_demo.py').read_text())
    rows=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='ROWS' for t in n.targets))
    assert bill['total']==185000 and len(bill['items'])==len(rows)==15
    expected=[rate*qty for _,_,rate,qty in rows]
    assert sorted(i['amount'] for i in bill['items'])==sorted(expected)
    review=[]
    for i,(description,category,rate,qty) in enumerate(rows):
        review.append({'description':description,'category':category,'rate':rate,'qty':qty,'amount':rate*qty,'page':i//5+1})
    call('/api/case/bill?workspace=example','PUT',{'items':review,'statedTotal':185000})
    report['billReviewBasis']='15 rows/rates/quantities/pages compared with the exact authored synthetic PDF fixture, amounts match; names remain blank.'
    if os.environ.get('CARENEST_REVIEW_BILL_EVIDENCE') == '1':
        result, elapsed = call('/api/case/bill/evidence?workspace=example','POST',{})
        report['billEvidence'] = {'requestSeconds':elapsed,'result':result};save()
        print('Bill evidence captured:',len(result.get('rows',[])),'rows',flush=True)
    questions=['Why was ₹20,000 deducted from my current claim? Examine each reason against my policy and tell me what evidence is missing.',
               'Does the room-rent reduction apply to the implant too?',
               'Who should I contact about the unexplained ₹4,800, and what exactly should I request?']
    for question in ([] if ONLY_BILL else questions):
        print('Capturing:',question,flush=True)
        try:
            result,elapsed=call('/api/copilot/ask?workspace=example','POST',{'question':question,'conversationId':'j0-kotak-review-20261017'})
        except urllib.error.HTTPError as exc:
            report['failedRequest']={'question':question,'httpStatus':exc.code,'detail':exc.read().decode()[:500]};save();raise
        report['turns'].append({'question':question,'requestSeconds':elapsed,'response':result});save()
        print('Captured:',result['answer']['headline'],f'({elapsed}s)',flush=True)
    if not ONLY_BILL:
        letter,elapsed=call('/api/case/letter?workspace=example&kind=clarification')
        report['letter']={'requestSeconds':elapsed,'draft':letter};save()
finally:
    try:
        request=urllib.request.Request(BASE+'/api/session?workspace=general',method='DELETE')
        with client.open(request,timeout=60) as response:report['cleanupStatus']=response.status
    finally: save()
print(json.dumps({'turns':len(report['turns']),'cleanupStatus':report.get('cleanupStatus'),'humanAccepted':False}))
