"""Conservative source-linked arithmetic. Unsupported document formats stay unknown."""
import hashlib
import re
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from pypdf import PdfReader
from app.services import case_store

NUMBER = r'([\d,]+(?:\.\d{1,2})?)'
IMPLANT = re.compile(r'(?:Recorded\s+)?implant calculation:\s*\(' + NUMBER +
    r'\s*-\s*(?:hospital\s+)?discount\s+' + NUMBER + r'\)\s*[x×]\s*\(1\s*-\s*' +
    NUMBER + r'\s*/\s*' + NUMBER + r'\)\s*=\s*' + NUMBER, re.I)
DISCOUNT = re.compile(r'Hospital discount\s*[-–]\s*implant only\s*(?:Rs\.?|INR|₹)?\s*' + NUMBER,re.I)


def decimal(value):
    result=Decimal(str(value).replace(',',''))
    if not result.is_finite() or result < 0: raise ValueError('Invalid monetary operand')
    return result


def source_pages(case, kind):
    docs=[doc for doc in case.get('documents',[]) if doc.get('type')==kind]
    if len(docs)!=1: return []
    doc=docs[0]
    if not str(doc.get('id','')).startswith('doc-'): return []
    data,mime=case_store.load_file(doc['id'])
    if mime!='application/pdf' or len(data)>20*1024*1024: return []
    digest=hashlib.sha256(data).hexdigest()
    if doc['id'] != 'doc-'+digest[:16]: return []
    pdf=PdfReader(BytesIO(data))
    if len(pdf.pages)>100: return []
    return [{'docId':doc['id'],'docHash':digest,'page':index,'text':page.extract_text() or '',
             'docName':kind,'docUrl':'/api/case/document/'+doc['id']} for index,page in enumerate(pdf.pages,1)]


def implant_trace(row, case, facts, scope, bills, decisions):
    trace={'version':'implant-recorded-ratio-v1','inputFingerprint':scope,'status':'needs_inputs',
           'billRows':[],'sources':[],'calculation':None,
           'missing':['An explicit implant bill-row binding, allocated discount and recorded calculation are required.'],
           'qualification':'A matching calculation does not establish policy applicability or entitlement to payment.'}
    items=[item for item in (case.get('bill') or {}).get('items',[])
           if item.get('category')=='implants' and re.search(r'implant',item.get('description',''),re.I)]
    if not (case.get('bill') or {}).get('reviewed') or len(items)!=1: return trace
    item=items[0]
    trace['billRows']=[{key:item.get(key) for key in ('id','description','amount','rate','qty','page')}]
    allocations=[(page,match) for page in bills for match in DISCOUNT.finditer(page['text'])]
    formulas=[(page,match) for page in decisions for match in IMPLANT.finditer(page['text'])]
    if len(allocations)!=1 or len(formulas)!=1: return trace
    bill_page,allocation=allocations[0]; decision_page,formula=formulas[0]
    gross,discount,eligible,actual,recorded=map(decimal,formula.groups())
    allocation_amount=decimal(allocation.group(1))
    room=(case.get('bill') or {}).get('roomRent') or {}
    selected=(facts.get('roomRent') or {}).get('amount')
    # No matching by amount alone, no allocation of a bill-wide discount by assumption.
    if (gross!=decimal(item['amount']) or discount!=allocation_amount or discount>gross
            or not actual or eligible>actual or selected is None or eligible!=decimal(selected)
            or room.get('ratePerDay') is None or actual!=decimal(room['ratePerDay'])
            or item.get('page')!=bill_page['page']
            or item['description'].casefold() not in bill_page['text'].casefold()):
        trace['missing']=['Confirm the bill row, explicit implant-only discount and daily rates: the recorded inputs do not match.']
        return trace
    net=gross-discount
    result=(net*(Decimal(1)-eligible/actual)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
    difference=result-decimal(row.amount)
    trace.update(status='reconciles' if difference==0 and result==recorded else 'mismatch',missing=[],
        calculation={'method':'net_implant_times_recorded_room_reduction','gross':str(gross),'discount':str(discount),
                     'net':str(net),'eligibleDailyRate':str(eligible),'actualDailyRate':str(actual),
                     'result':str(result),'decisionAmount':str(row.amount),'difference':str(difference),
                     'formula':f'({gross} - {discount}) × (1 - {eligible}/{actual}) = {result}',
                     'rateOrigin':'Fictional selected eligibility; not established by the original policy wording' if facts.get('demoAssumptions') else 'Recorded policy selection; schedule applicability still requires confirmation'})
    trace['sources']=[{**{key:page[key] for key in ('docId','docName','docHash','page','docUrl')},'quote':match.group(0)}
                      for page,match in ((bill_page,allocation),(decision_page,formula))]
    return trace


def attach_evidence(review, case, facts, scope):
    targets=[row for row in review.rows if re.search(r'implant',row.label,re.I)]
    if not targets: return
    try:
        bills=source_pages(case,'Hospital bill');decisions=source_pages(case,'Settlement letter')
        for row in targets:
            row.evidence=implant_trace(row,case,facts,scope,bills,decisions)
    except Exception:
        # A missing/unreadable original never turns into a guessed allocation or ratio.
        for row in targets:
            row.evidence={'version':'implant-recorded-ratio-v1','inputFingerprint':scope,'status':'needs_inputs',
                          'billRows':[],'sources':[],'calculation':None,'missing':['Original source documents could not be checked.'],
                          'qualification':'No source-linked calculation is confirmed.'}
