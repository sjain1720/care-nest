"""Pre-admission source facts and date/room arithmetic. No clinical or payout verdict."""
from decimal import Decimal
from datetime import datetime
from zoneinfo import ZoneInfo
from app.schemas import TreatmentPlanInput, TreatmentPlanPreparation, PlannedWaitingPeriod, PlannedRoomRisk
from app.services import policy_store
from app.services.waiting_periods import parse_date, status


def prepare_plan(body: TreatmentPlanInput, facts: dict | None) -> TreatmentPlanPreparation:
    common = {'procedure': body.procedure.strip(), 'plannedAdmission': body.plannedAdmission.isoformat() if body.plannedAdmission else None}
    if not facts:
        return TreatmentPlanPreparation(status='needs_policy', **common,
            questionsToConfirm=['Upload the policy and its schedule before assessing this planned treatment.'])
    questions = ['Confirm the procedure, insured member, medical history and applicable policy benefits with the insurer before relying on a coverage answer.']
    warnings = ['These are date comparisons and recorded limits, not a coverage or cashless approval decision. Continuity, endorsements, medical history and other terms may change applicability.']
    planned = body.plannedAdmission
    if not planned:
        questions.append('What is the planned admission date?')
    elif planned < datetime.now(ZoneInfo('Asia/Kolkata')).date():
        warnings.append('The entered admission date is in the past; confirm it if you are planning a future treatment.')
    waits = []
    for period in facts.get('waitingPeriods', []):
        end = parse_date(period.get('endDate'))
        comparison = status(end, planned) if planned else None
        state = 'end_date_unknown' if not end else 'planned_date_missing' if not planned else 'ends_by_planned_date' if comparison['over'] else 'running_on_planned_date'
        waits.append(PlannedWaitingPeriod(label=period['label'], appliesTo=period.get('appliesTo') or 'Confirm applicability',
            endDate=end.isoformat() if end else None, dateStatus=state,
            daysRemainingAtAdmission=comparison['daysLeft'] if comparison else None, citation=period.get('citation')))
    if not facts.get('startDate') or any(w.dateStatus == 'end_date_unknown' for w in waits):
        questions.append('Confirm the inception/continuity date and applicable waiting-period end dates from the schedule and insurer.')
    if not waits:
        questions.append('The extracted facts do not list waiting periods. Check the wording; do not assume there are none.')
    room = None
    limit = facts.get('roomRent') or {}
    supported_unit = (limit.get('unit') or '').lower().strip() in ('per day', '/day', 'per_day', 'day')
    if body.normalRoomRatePerDay is not None:
        amount = limit.get('amount')
        if facts.get('productType') != 'health_indemnity' or not supported_unit or amount is None or amount <= 0:
            questions.append('A monetary normal-room daily limit is not established for this product. Confirm the applicable room benefit before comparing prices.')
        else:
            proposed, eligible = Decimal(str(body.normalRoomRatePerDay)), Decimal(str(amount))
            excess = max(Decimal('0'), proposed - eligible).quantize(Decimal('0.01'))
            room = PlannedRoomRisk(status='above_recorded_limit' if excess else 'within_recorded_limit',
                recordedLimitPerDay=float(eligible), proposedRatePerDay=float(proposed), dailyExcess=float(excess), citation=limit.get('citation'))
            if excess:
                questions.append('Ask which other expense categories would be affected by choosing this room and request a room within the applicable limit.')
    else:
        questions.append('What is the hospital quote for the normal room per day? ICU eligibility needs a separate benefit check.')
    questions.append('Confirm member-specific co-pay, deductibles, sub-limits, hospital network eligibility and pre-authorisation requirements in writing.')
    return TreatmentPlanPreparation(status='prepared', **common, waitingPeriods=waits, roomRisk=room,
        coPay=facts.get('coPay'), deductible=facts.get('deductible'), questionsToConfirm=questions, warnings=warnings)


def current_plan(body):
    active = policy_store.get_active_policy()
    return prepare_plan(body, active[1]['facts'] if active else None)
