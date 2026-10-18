"""Prepare source inputs for dispute review; no generated explanation is evidence."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from app.schemas import DisputePreparation, DisputeInputIssue, DisputeReconciliation
from app.services import case_store, policy_store
from app.services.settlement_checks import has_reason


def _money(value):
    if value is None or isinstance(value, bool):
        raise ValueError('An extracted amount is missing or invalid.')
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0:
            raise ValueError('Amounts must be finite and non-negative.')
        return amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise ValueError('An extracted amount is invalid.') from exc


def prepare_dispute(case: dict, policy_id: str | None) -> DisputePreparation:
    """Readiness is not approval or a finding that a deduction is justified."""
    issues, warnings = [], []
    bill, settlement, rejection = case.get('bill'), case.get('settlement'), case.get('rejection')
    decision = 'conflicting' if settlement and rejection else 'settlement' if settlement else 'rejection' if rejection else 'none'

    def missing(code, message, route='/upload'):
        issues.append(DisputeInputIssue(code=code, message=message, route=route))

    if not policy_id:
        missing('policy_missing', 'Add the policy that applies to this claim.')
    elif case.get('policyId') != policy_id:
        missing('policy_link_unconfirmed', 'The selected policy is not linked to this claim. Confirm the correct policy before comparing its clauses.', '/case')
    if decision == 'none':
        missing('decision_missing', "Add the insurer's settlement or rejection letter.")
    elif decision == 'conflicting':
        missing('decision_conflict', 'Both a settlement and a rejection are recorded. Confirm which decision this review should examine.', '/case')
    if settlement and not bill:
        missing('bill_missing', 'Add the itemized hospital bill to compare deducted charges.')
    if bill and bill.get('reviewed') is not True:
        missing('bill_unreviewed', 'Review the extracted bill rows and amounts before relying on the comparison.', '/case/bill')
    if rejection and not has_reason(rejection.get('reason')):
        warnings.append('The rejection has no clear stated reason. Ask the insurer for its reason and applicable clause in writing.')
    if not any(d.get('type') == 'Discharge summary' for d in case.get('documents', [])):
        warnings.append('No discharge summary is recorded. Treatment or medical-history questions may require additional evidence.')

    reconciliation, unexplained = None, []
    if settlement:
        deductions = settlement.get('deductions', [])
        try:
            claimed, approved = _money(settlement.get('claimedAmount')), _money(settlement.get('approvedAmount'))
            amounts = [_money(d.get('amount')) for d in deductions]
            itemized = sum(amounts, Decimal('0.00'))
            gap = claimed - approved - itemized
            reconciliation = DisputeReconciliation(claimedAmount=float(claimed), approvedAmount=float(approved),
                decisionDifference=float(claimed - approved), itemizedDeductions=float(itemized),
                unexplainedGap=float(gap), arithmeticOk=gap == 0)
            if approved > claimed:
                missing('approved_exceeds_claimed', 'The approved amount exceeds the claimed amount. Confirm the extracted figures.', '/case/settlement')
            if gap:
                warnings.append('Claimed minus approved does not equal the itemized deductions. Ask for the reconciliation; the difference is not automatically an additional payable amount.')
            unexplained = [d.get('id', '') for d in deductions if not has_reason(d.get('insurerReason'))]
        except ValueError:
            missing('amounts_invalid', 'Some extracted settlement amounts are missing or invalid. Confirm them against the decision letter.', '/case/settlement')
    available = sorted({d.get('type') for d in case.get('documents', []) if d.get('type')})
    return DisputePreparation(status='needs_inputs' if issues else 'ready_for_review', decision=decision,
        availableDocuments=available, missingInputs=issues, warnings=warnings,
        reconciliation=reconciliation, deductionsWithoutReason=unexplained)


def current_dispute_inputs() -> DisputePreparation:
    return prepare_dispute(case_store.get_case(), policy_store.get_active_policy_id())
