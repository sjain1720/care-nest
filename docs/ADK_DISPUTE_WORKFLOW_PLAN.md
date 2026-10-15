# First ADK workflow unexplained deductions and rejection

User-selected priority, 14 October 2026. Cashless queries and pre-admission cost
planning remain subsequent features. Implementation window: 14–16 October; video on 17 October; submission deadline on 18 October.

## User outcome

For a question such as “Why was ₹38,000 deducted?”, inspect the visitor's actual
uploaded documents, reconcile available amounts, ask targeted missing questions,
examine each reason against the selected policy, and produce an evidence-backed
explanation, document/action checklist and editable clarification/reconsideration
letter. ₹38,000 is an example, never a hardcoded result.

## Stage 1 document checks and calculations

Local implementation: `GET /api/case/dispute/inputs` and a preparation panel on
the settlement/rejection page. Seven targeted checks and the full 136-test backend
suite pass; production frontend build passes. No ADK execution or production
deployment claimed.

Add a typed, guest-scoped preparation endpoint. Identify available policy, bill and
settlement/rejection; missing/unreviewed inputs; policy/claim mismatch; conflicting
decision records and deductions with no stated reason. Compute arithmetic in code.
Do not call an amount match proof of coverage or treat stored AI explanations as
source facts. Fix the existing UI wording that equates stated reasons with policy
support. This stage prepares the ADK inputs; it is not an ADK launch.

## Stage 2 coordinated ADK evidence review

Use controlled execution: document snapshot → policy specialist → deduction/rejection
analyst → mandatory verifier. Share bounded, structured evidence in workflow state.
Agents can retrieve applicable clauses and request missing facts. Calculation and
ownership checks are code tools. Every agent result must identify source references;
exact quote checking plus semantic support review is mandatory. A model cannot skip
verification. Reject fabricated sources, unrelated clauses and approval promises.
Scope each run to guest, selected policy and current claim. Do not reuse the current
experimental ADK runner's fixed internal `demo` identity as persisted guest context.
Bound tool/model calls and execution time; surface unavailable/partial results.

## Stage 3 action plan and draft

For each unresolved issue, specify the question, whom to ask, the document/evidence
that would help and why. Separate insurer-requested papers, policy requirements and
our suggested clarification evidence. Preserve collected/requested status. Never
present suggestions as mandatory insurer requirements. Reuse the letter editor;
validate amounts, source facts and placeholders, and include the evidence index.
Human review precedes sending; this application does not submit claims or complaints.
Do not state statutory escalation deadlines without official verification.

## Stage 4 integration and acceptance

Stream actual specialist/tool/verification progress and render a structured result.
Start with this selected workflow; keep ordinary/general questions on the working
baseline until comparison supports a broader switch. A fallback must be labelled,
not presented as an ADK success. Record execution path and evaluated release.

Acceptance cases: correct partial settlement; arithmetic discrepancy; no stated
reason; rejection with missing medical evidence; irrelevant policy clause; missing
policy/bill/decision; unreviewed extracted amounts; wrong policy association;
conflicting decision records; another guest; document prompt injection; failed
model/tool call; user clarification and policy switch. A successful workflow should
produce useful questions even when it cannot confirm a deduction's applicability.

Use existing synthetic demo files first. Detailed reports remain ignored. No new
training job, account system, reminders, recommendations or insurer integration is
part of this first workflow. The earlier 9–16 hour estimate remains a rough estimate
for one evaluated workflow; live deployment requires passing the acceptance gates.


## Dated checkpoints

- 14 October: source gate/reconciliation and controlled ADK pipeline integration.
- 15 October: deduction/rejection evidence review, targeted questions, personalized
  action checklist and editable letter; wire actual progress into the user workflow.
- 16 October: compare against baseline on acceptance cases, fix failures, deploy
  the verified scope, inspect phone/desktop and rehearse. Preserve a synthetic fallback.
- 17 October: record the demo video using the verified release.
- 18 October: submission deadline.

This is a target schedule, not a guarantee. If evidence quality or session isolation
fails, narrow the demonstrated scope instead of claiming the unverified path works.
