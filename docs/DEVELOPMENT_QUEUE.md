# CareNest development queue — 14 October 2026

Start with `REPO_MAP.md`. `FEATURE_PLAN_STATUS.md` maps the original five features
and build phases to actual code. `AI_QUALITY_REPORT.md` records release checks;
`TUNING_COMPARISON.md` records the completed experiment. Historical handoffs are
not current acceptance evidence.

## Confirmed scope

Finish the five core features: policy explanation, bill analysis, claim preparation,
rejection/deduction assistance and waiting-period/PED tracking, with a unified journey.
Defer recommendations, automatic alerts, accounts/family profiles, insurer APIs and
complete benefit accounting until after the hackathon.

## Latest completed checks

- Backend coverage, reviewed bill-row policy evidence and bounded guest-scoped
  follow-up context are implemented. 129 backend tests pass.
- Semantic support guard: unchanged benchmark 11/12 verdict, 12/12 citation checks.
  The old diabetes reference assumes PED without onset facts; corrected v2 rescoring
  yields 12/12 verdict checks on the same outputs, not an independent evaluation.
- Follow-up verification passed six storage/isolation checks. One date follow-up
  was withheld by the stricter support guard; completeness still needs improvement.
- Existing tuning job succeeded. Both arms completed 34 held-out questions: baseline
  33/34 and tuned 34/34 exact quotes. Keep the baseline live pending broader evidence.
- Scheduled cleanup worker succeeded at 03:00 India time using the v7 image, with
  0 removed/0 failed. No manual multi-tenant deletion was run.
- Node build image upgraded to 24. Revision `carenest-00008-7wp` is deployed with the support guard and serves 100%
  traffic. The cleanup job image is synchronized; last verified scheduled run used v7.

## Remaining application work, in order

1. Make claim preparation fit cashless/reimbursement and selected-policy requirements;
   incorporate actual insurer document requests with traceable sources. The current
   default checklist is mostly generic reimbursement guidance.
2. Strengthen each deduction explanation's semantic evidence before labeling it
   supported; link a reason-specific checklist/action plan to verified policy and
   bill/settlement facts. Verify official escalation deadlines before presenting them.
3. Improve grounded clarification answers without weakening safe abstention. Review
   broader unseen policies and realistic claims with onset/schedule/rider unknowns.
4. Complete explicit demo reset/mode switching and the desktop/phone walkthrough;
   test blurred/cropped synthetic bill images and prepare a backup judging video.
5. Before broader private use, inventory legacy unowned records and harden deletion
   during in-flight uploads/AI writes. Do not blindly delete legacy data.

## Verification strategy

Keep fast tests for arithmetic, ownership, source integrity and API compatibility.
Run a synthetic real-cloud workflow after a meaningful release, not after every
styling edit. `eval/verify_followup.py` checks bounded context and policy switches;
`eval/evaluate_live.py --questions eval/golden_questions_v2.jsonl` selects the updated
expectations. Generated labels, reports and credentials remain ignored.


## Selected next workflow and schedule

User selected unexplained deductions/rejection first. Work window 14–16 October;
video on 17 October and submission on 18 October. Follow
`ADK_DISPUTE_WORKFLOW_PLAN.md` rather than adding other features in parallel.

Stage 1 source preparation is implemented locally: guest-scoped typed endpoint,
missing/unreviewed input checks, wrong-policy/conflicting-decision checks, decimal
reconciliation, and a settlement/rejection page preparation panel. Stated reasons
are no longer described as matching policy rules in the page summary. Seven new
checks pass, 136 backend tests total; frontend production build passes. This is
preparation for ADK, not execution
of the coordinated agents, and has not been deployed.

Next: controlled ADK policy-evidence and deduction review, mandatory verification,
personalized clarification checklist/letter and end-to-end comparison. Retain the
working live path until those acceptance gates pass.
