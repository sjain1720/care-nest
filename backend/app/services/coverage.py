"""Deterministic recorded-claims estimate; Gemini never calculates a balance."""
from calendar import monthrange
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def get_guest_coverage():
    from app.services import policy_store, case_store
    from app.services.claim_history import has_content, summarize_case
    active = policy_store.get_active_policy()
    current = case_store.get_case()
    ledger = ([summarize_case(current, 'current')] if has_content(current) else []) + case_store.list_past_claims()
    return estimate_coverage(active[1]['facts'] if active else None, ledger,
                             demo=bool(active and active[1].get('isDemoTemplate')))


def coverage_answer(language='en'):
    from app.schemas import AnswerCard, NextAction
    result = get_guest_coverage()
    if result['status'] != 'recorded_only':
        return AnswerCard(verdict='cant_confirm', headline='More policy details are needed',
                          summary=result['warnings'][0], citations=[], toConfirm=[],
                          nextAction=NextAction(label='Check policy details', route='/policy'))
    from app.services.policy_details import format_inr
    summary = (f"Base sum insured {format_inr(result['sumInsured'])}, minus linked recorded payments "
               f"{format_inr(result['used'])}, gives an estimated {format_inr(result['remaining'])} remaining. "
               "This does not establish your insurer's actual balance; history and restoration benefits may be incomplete.")
    if language == 'hi':
        summary = (f"बीमा राशि {format_inr(result['sumInsured'])} में से दर्ज भुगतान {format_inr(result['used'])} "
                   f"घटाने पर अनुमानित शेष {format_inr(result['remaining'])} है। यह बीमाकर्ता का आधिकारिक शेष नहीं है; "
                   "पुराने क्लेम और रिस्टोरेशन लाभ की जानकारी अधूरी हो सकती है।")
    return AnswerCard(verdict='info', headline='Estimate from your recorded claims', summary=summary,
                      citations=[], toConfirm=['Confirm your full claim history and available balance with the insurer.'],
                      nextAction=NextAction(label='See the calculation', route='/policy'))


def _date(value):
    try:
        return date.fromisoformat(value) if value else None
    except (TypeError, ValueError):
        return None


def _money(value):
    try:
        amount = Decimal(str(value))
        return amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if amount.is_finite() and amount >= 0 else None
    except (TypeError, ValueError, InvalidOperation):
        return None


def policy_year(start: date, today: date):
    def anniversary(year):
        return date(year, start.month, min(start.day, monthrange(year, start.month)[1]))
    year = today.year if anniversary(today.year) <= today else today.year - 1
    return anniversary(year), anniversary(year + 1) - timedelta(days=1)


def estimate_coverage(policy: dict | None, claims: list[dict], today: date | None = None, demo=False):
    today = today or datetime.now(ZoneInfo("Asia/Kolkata")).date()
    result = dict(status='missing_policy', policyId=None, asOf=today.isoformat(), year=None,
                  sumInsured=None, used=None, remaining=None, pct=None, counted=[], excluded=[],
                  pending=False, floater=False, demo=demo, historyComplete=False,
                  warnings=["This is an estimate from recorded claims, not the insurer's official balance.",
                            "Assumes annual uninterrupted renewal from the entered policy start date.",
                            "Restoration benefits, sub-limits, co-pay, deductibles and missing claims can change availability."])
    if not policy:
        result['warnings'].insert(0, 'Select or upload a policy first.')
        return result
    result['policyId'] = policy.get('policyId')
    if policy.get('productType', 'health_indemnity') != 'health_indemnity':
        result['status'] = 'unsupported_product'
        result['warnings'].insert(0, 'This product is not a health-indemnity policy; subtracting claims may not describe its benefits.')
        return result
    result['floater'] = 'floater' in (policy.get('policyType') or '').lower()
    insured = _money(policy.get('sumInsured'))
    if not insured:
        result['status'] = 'missing_sum_insured'
        result['warnings'].insert(0, 'Add the sum insured from your policy schedule.')
        return result
    result['sumInsured'] = float(insured)
    start = _date(policy.get('startDate'))
    if not start:
        result['status'] = 'missing_start_date'
        result['warnings'].insert(0, 'Add a valid policy start date to determine the current policy year.')
        return result
    if start > today:
        result['status'] = 'not_started'
        result['warnings'].insert(0, 'The policy start date is in the future.')
        return result
    first, last = policy_year(start, today)
    result['year'] = {'from': first.isoformat(), 'to': last.isoformat()}
    used = Decimal('0')
    seen_ids, seen_numbers = set(), set()
    for claim in claims:
        reason = None
        if not claim.get('policyId'):
            reason = 'policy_link_missing'
        elif claim['policyId'] != result['policyId']:
            reason = 'different_policy'
        elif claim.get('status') not in ('paid', 'part_paid'):
            reason = 'not_paid'
            result['pending'] |= claim.get('status') == 'in_progress'
        else:
            when, amount = _date(claim.get('date')), _money(claim.get('approvedAmount'))
            if not when:
                reason = 'date_missing_or_invalid'
            elif when > today:
                reason = 'future_claim_date'
            elif not first <= when <= last:
                reason = 'outside_policy_year'
            elif amount is None:
                reason = 'invalid_amount'
            elif claim.get('id') in seen_ids or (claim.get('claimNumber') and claim['claimNumber'].strip().casefold() in seen_numbers):
                reason = 'duplicate_claim'
            else:
                used += amount
                seen_ids.add(claim.get('id'))
                if claim.get('claimNumber'):
                    seen_numbers.add(claim['claimNumber'].strip().casefold())
                result['counted'].append({**{key: claim.get(key) for key in ('id', 'title', 'date')}, 'approvedAmount': float(amount)})
        if reason:
            result['excluded'].append({'id': claim.get('id', ''), 'reason': reason})
    remaining = max(Decimal('0'), insured - used)
    result.update(status='recorded_only', used=float(used), remaining=float(remaining),
                  pct=int((100 * remaining / insured).quantize(Decimal('1'), rounding=ROUND_HALF_UP)))
    if result['excluded']:
        result['warnings'].insert(0, 'Some records were excluded. Check their policy link, dates and payment status.')
    if used > insured:
        result['warnings'].insert(0, 'Recorded payments exceed the base sum insured; check duplicates, dates and restoration benefits.')
    if not demo:
        result['warnings'].insert(0, 'Insufficient claim history to determine current insurer balance. Only linked recorded claims are counted.')
    return result
