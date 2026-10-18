"""One deterministic financial view; unknown amounts and receipt remain distinct."""
import math
from app.services.claim_tracker import sorted_timeline


def amount(value):
    if isinstance(value, bool):
        return None
    try:
        n = float(value)
        return n if math.isfinite(n) and 0 <= n <= 100_000_000 else None
    except (ValueError, TypeError):
        return None


def effective_case(case):
    result = dict(case)
    s = case.get('settlement') or {}
    if s and s.get('letterType') in ('query', 'other'):
        result['settlement'] = None
        result['legacyDecisionNeedsReview'] = True
    current = result.get('settlement') or result.get('rejection') or {}
    decision_date = current.get('letterDate') or ''
    for e in sorted_timeline(case.get('timeline')):
        n = amount(e.get('newApprovedAmount'))
        if (e.get('kind') == 'reply' and e.get('outcome') == 'paid_more' and not e.get('responseVersion')
                and n is not None and (not decision_date or (e.get('date') or '') >= decision_date)):
            existing = result.get('settlement') or {}
            if existing.get('approvedAmount') != n:
                result['settlement'] = {**existing, 'approvedAmount':n,
                    'claimedAmount':existing.get('claimedAmount'), 'billedAmount':existing.get('billedAmount'),
                    'claimNumber':existing.get('claimNumber',''), 'letterDate':e.get('date',''),
                    'deductions':[], 'reconciliation':None, 'docUrl':e.get('docUrl'),
                    'letterType':'settlement', 'approvalFromReply':True}
                result['rejection'] = None
            decision_date = e.get('date') or decision_date
    return result


def financials(case):
    case = effective_case(case)
    s, rejection, bill = (case.get(k) or {} for k in ('settlement', 'rejection', 'bill'))
    claimed = amount(s.get('claimedAmount'))
    approved = amount(s.get('approvedAmount')) if s else 0.0 if rejection else None
    decision_type = 'settlement' if s else 'rejection' if rejection else 'none'
    decision_date = (s or rejection).get('letterDate') or ''
    for e in sorted_timeline(case.get('timeline')):
        # New document responses are reconciled by the ingestion boundary. Legacy
        # explicit approval replies can supplement an older decision, never a newer one.
        if e.get('kind') == 'reply' and e.get('outcome') == 'paid_more' and not e.get('responseVersion'):
            n = amount(e.get('newApprovedAmount'))
            if n is not None and (not decision_date or (e.get('date') or '') >= decision_date):
                approved = n
                decision_type = 'settlement'
    receipts = [e for e in sorted_timeline(case.get('timeline')) if e.get('kind') == 'payment_recorded']
    received = amount(receipts[-1].get('paymentAmount')) if receipts else None
    return {'billedAmount': amount(bill.get('total')), 'claimedAmount': claimed,
            'approvedAmount': approved, 'receivedAmount': received,
            'decisionType': decision_type, 'decisionAvailable': decision_type != 'none',
            'needsReview': bool(case.get('legacyDecisionNeedsReview'))}


def settlement_view(case):
    case = effective_case(case)
    s = case.get('settlement')
    if not s:
        return None
    return {**s, 'approvedAmount': financials(case)['approvedAmount']}
