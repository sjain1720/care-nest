"""Record insurer communications without turning interim queries into decisions."""
from datetime import date
from app.services import case_store
from app.services.claim_tracker import new_event_id
from app.services.claim_financials import amount, effective_case
from app.services.deduction_explainer import explain_deductions
from app.services.privacy import mask_all
from app.services.settlement_checks import reconcile

RESPONSE_VERSION = 2


def record_response(ext, doc_url=None, source='pdf', doc_id=None, quote=''):
    try:
        if ext.letterDate:
            ext.letterDate = date.fromisoformat(ext.letterDate).isoformat()
    except ValueError:
        ext.letterDate = None
    kind = ext.letterType
    outcome = ('asks_for_papers' if kind == 'query' else 'rejected' if kind == 'rejection'
               else 'paid_more' if kind == 'settlement' and amount(ext.approvedAmount) is not None
               else ext.replyOutcome if kind == 'other' and ext.replyOutcome in ('explained','no_change') else 'unclear')
    summary = ext.summary or {'query':'The insurer requested more information before deciding.',
        'settlement':'The insurer sent a settlement decision. Review the approved amount and conditions.',
        'rejection':'The insurer sent a rejection. Review its stated reason.',
        'other':'This communication does not establish a new settlement or rejection.'}[kind]
    when = ext.letterDate or date.today().isoformat()
    event = mask_all({'id':new_event_id(), 'kind':'reply', 'date':when, 'outcome':outcome,
        'summary':summary, 'papersAsked':ext.papersAsked if kind == 'query' else [],
        'reference':ext.referenceNumber or ext.claimNumber, 'source':source, 'docUrl':doc_url,
        'communicationType':kind, 'responseVersion':RESPONSE_VERSION, 'quote':quote})
    if kind == 'settlement' and amount(ext.approvedAmount) is not None:
        event['newApprovedAmount'] = amount(ext.approvedAmount)

    def apply(raw):
        case_store.check_flow(raw)
        case = effective_case(raw)
        patch = {'timeline':case.get('timeline', []) + [event]}
        current = case.get('settlement') or case.get('rejection') or {}
        current_date = current.get('letterDate') or ''
        # Undated or older documents never silently replace a dated decision.
        newer = not current_date or bool(ext.letterDate and ext.letterDate >= current_date)
        if raw.get('settlement') and raw['settlement'].get('letterType') in ('query','other'):
            patch['settlement'] = None  # Explicitly known old misclassification, originals retained.
        if kind in ('settlement','rejection') and newer:
            if kind == 'rejection':
                patch.update(settlement=None, rejection={'reason':ext.rejectionReason or '',
                    'page':ext.rejectionReasonPage or 1, 'claimNumber':ext.claimNumber or '',
                    'letterDate':ext.letterDate or '', 'docUrl':doc_url, 'docId':doc_id})
            else:
                deductions = [{'id':f'd{i}', 'label':d.label, 'amount':d.amount,
                    'insurerReason':d.insurerReason, 'page':d.page, 'docId':doc_id,
                    'docUrl':doc_url} for i,d in enumerate(ext.deductions,1)]
                explained = explain_deductions(deductions, case.get('bill')) if deductions else []
                claimed, approved = amount(ext.claimedAmount), amount(ext.approvedAmount)
                patch.update(rejection=None, settlement={'claimNumber':ext.claimNumber or '',
                    'letterDate':ext.letterDate or '', 'docId':doc_id, 'docUrl':doc_url,
                    'billedAmount':amount((case.get('bill') or {}).get('total')),
                    'claimedAmount':claimed, 'approvedAmount':approved,
                    'deductions':explained, 'letterType':'settlement', 'responseVersion':RESPONSE_VERSION,
                    'reconciliation':reconcile(claimed, approved, explained) if claimed is not None and approved is not None else None})
        return patch
    case_store.mutate_case(apply)
    return {**event, 'detectedType':'Settlement letter' if kind == 'settlement' else 'Rejection letter' if kind == 'rejection' else 'Insurer reply'}
