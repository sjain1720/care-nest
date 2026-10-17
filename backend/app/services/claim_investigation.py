"""Normal-chat adapter and scoped, deterministic artifacts from verified ADK rows."""
import re
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone
from app.schemas import AnswerCard, AskResponse, NextAction
from app.services import case_store, policy_store
from app.services.dispute_review import run_review, snapshot
from app.services.case_builder import build_case
from app.services.letters import letter_facts, template_body
from app.core.session import session_id
from app.core.gcp import db


def wants_investigation(question):
    text = question.lower()
    decision = re.search(r'deduct|settle|paid less|reject|repudiat|कटौती|दावा.*खारिज', text)
    action = re.search(r'why|investigat|explain each|check.*policy|clarif|appeal|challenge|reconsider|क्यों', text)
    return bool(decision and action) and not re.search(r'what (?:is|does).*deduction|in general', text)


def money(value):
    amount = Decimal(str(value)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
    from app.services.policy_details import format_inr
    sign = '−' if amount < 0 else ''
    amount = abs(amount)
    whole = int(amount)
    cents = int((amount - whole) * 100)
    return sign + format_inr(whole) + (f'.{cents:02d}' if cents else '')


def refine_questions(review, case):
    """Avoid asking again for room itemization explicitly confirmed in this snapshot."""
    bill = case.get('bill') or {}
    room_present = bill.get('reviewed') and any(i.get('category') == 'room' for i in bill.get('items', []))
    if not room_present:
        return
    for row in review.rows:
        row.missingInformation = [
            'Ask the insurer to identify the reviewed bill rows included in its room-related reduction and show the calculation.'
            if re.search(r'itemi[sz]ed room|room rent charges.*bill', question, re.I) else question
            for question in row.missingInformation]


def correspondence_request(question):
    """Convert action instructions to correspondence without adding new findings."""
    text = question.strip()
    text = re.sub(r'^ask (?:the |your )?insurer (?:for|to provide) ', 'Please provide ', text, flags=re.I)
    text = re.sub(r'^ask (?:the |your )?insurer to ', 'Please ', text, flags=re.I)
    if re.match(r'can you provide ', text, re.I):
        text = re.sub(r'^can you provide ', 'Please provide ', text, flags=re.I).rstrip('?') + '.'
    if re.match(r'do you have the discharge summary', text, re.I):
        return 'Please confirm the hospital-stay duration used in your calculation and identify any supporting discharge evidence you still require.'
    text = re.sub(r'\byour plan\b', 'this policy', text, flags=re.I)
    text = re.sub(r'\byour policy schedule\b', 'the policy schedule', text, flags=re.I)
    text = re.sub(r',? and compare (?:them|it) with the original decision letter\.?', '.', text, flags=re.I)
    if not re.match(r'please\b', text, re.I):
        return 'Please clarify the following evidence or calculation question: ' + text
    return text


def action_plan(review):
    actions = []
    for row in review.rows:
        for question in row.missingInformation:
            owner = 'Insurer / TPA claims desk'
            if re.search(r'hospital|billing|room availability', question, re.I):
                owner = 'Hospital billing / admission desk'
            if re.search(r'treating (?:doctor|clinician)|medical history|onset', question, re.I):
                owner = 'Patient and treating clinician'
            actions.append({'rowId': row.id, 'question': question, 'source': owner,
                'why': f'Clarify the evidence or calculation for {row.label}.',
                'status': 'missing', 'basis': 'Suggested clarification; not an insurer-required document'})
    return actions


def build_draft(review, case, facts):
    kind = 'reconsideration' if review.preparation.decision == 'rejection' else 'clarification'
    # Old generated trust labels/citations must not leak into the new draft facts.
    clean = {**case, 'settlement': {**(case.get('settlement') or {}), 'deductions': []}}
    base = letter_facts(kind, {**build_case(clean), 'settlement': clean['settlement'],
                             'bill': case.get('bill'), 'rejection': case.get('rejection')}, facts)
    points = []
    reconciliation = review.preparation.reconciliation
    if reconciliation:
        points.append(f'The letter records {money(reconciliation.claimedAmount)} claimed and '
            f'{money(reconciliation.approvedAmount)} approved: a difference of {money(reconciliation.decisionDifference)}. '
            f'Itemized deductions total {money(reconciliation.itemizedDeductions)}.')
        if not reconciliation.arithmeticOk:
            points.append(f'Please reconcile the unexplained arithmetic gap of {money(reconciliation.unexplainedGap)}; I am not treating it as a confirmed deduction.')
    else:
        points.append('Please review the stated rejection reason and explain the applicable policy wording and facts relied upon.')
    evidence = [f"{doc['type']}: {doc.get('name', 'original document')}" for doc in case.get('documents', [])]
    for row in review.rows:
        label = row.label + (f' ({money(row.amount)})' if row.amount is not None else '')
        points.append(label + ': ' + (row.explanation + ' ' if row.assessment == 'related_wording' else '') + ' '.join(correspondence_request(q) for q in row.missingInformation))
        for citation in row.citations:
            entry = f'Policy wording — {citation.clause}, page {citation.page}: "{citation.quote}"'
            if entry not in evidence: evidence.append(entry)
    base.update(points=points, evidenceIndex=evidence)
    body = template_body(base).replace('The documents listed in the evidence index are attached.',
        'The evidence index identifies available source documents. Please confirm which copies or additional records you require.')
    return {'kind': kind, 'to': base['to'], 'subject': base['subject'], 'body': body,
            'evidenceIndex': evidence, 'warnings': ['Review the original documents, fill placeholders and edit before sending. This app does not submit this letter.']}


def cached_draft(kind):
    case = case_store.get_case()
    artifact = case.get('disputeInvestigation') or {}
    draft = artifact.get('draft') or {}
    if draft.get('kind') == kind and artifact.get('scope') == snapshot()['scope']:
        return draft
    return None


async def investigate(question, on_step=None):
    initial_scope = snapshot()['scope']
    review = await run_review(question, on_step)
    if review.status == 'needs_inputs':
        card = AnswerCard(verdict='cant_confirm', headline='More documents or confirmation are needed',
            summary='I cannot investigate this decision reliably until the missing inputs are resolved.',
            citations=[], toConfirm=[i.message for i in review.preparation.missingInputs],
            nextAction=NextAction(label='Review claim inputs', route='/case'), investigation=review)
    elif review.status != 'reviewed':
        card = AnswerCard(verdict='cant_confirm', headline='Investigation incomplete',
            summary='The investigation could not be completed safely. No verified agent explanation is claimed.',
            citations=[], toConfirm=review.warnings, nextAction=NextAction(label='Open existing document checks', route='/case/settlement'), investigation=review)
    else:
        refine_questions(review, case_store.get_case())
        review.actions = action_plan(review)
        reconciliation = review.preparation.reconciliation
        summary = ('The insurer recorded ' + money(reconciliation.approvedAmount) + ' approved out of '
            + money(reconciliation.claimedAmount) + ' claimed; the difference is '
            + money(reconciliation.decisionDifference) + '. ' if reconciliation else 'The recorded decision is a rejection. ')
        summary += 'Review the findings and the evidence still needed below.'
        citations = []
        for row in review.rows:
            for citation in row.citations:
                if citation not in citations: citations.append(citation)
        card = AnswerCard(verdict='needs_checking', headline='Claim investigation: evidence and next steps',
            summary=summary, citations=citations, toConfirm=[], investigation=review,
            nextAction=NextAction(label='Edit the evidence-based letter', route='/case/letter'))
        # Never persist findings/draft if documents changed or the guest was revoked.
        identity = db().collection('guestSessions').document(session_id()).get()
        record = identity.to_dict() or {}
        deadline = record.get('expiresAt')
        active_guest = identity.exists and not record.get('revoked') and isinstance(deadline, datetime) and deadline > datetime.now(timezone.utc)
        if active_guest and initial_scope == snapshot()['scope']:
            case = case_store.get_case(); active = policy_store.get_active_policy()
            draft = build_draft(review, case, active[1].get('facts', {}) if active else {})
            case_store.update_case({'disputeInvestigation': {'scope': initial_scope,
                'review': review.model_dump(), 'draft': draft}})
        else:
            return AskResponse(steps=review.steps, answer=AnswerCard(verdict='cant_confirm',
                headline='Inputs changed during investigation', summary='Run the investigation again for the current policy and claim.',
                citations=[], toConfirm=[], nextAction=None))
    return AskResponse(steps=review.steps, answer=card)
