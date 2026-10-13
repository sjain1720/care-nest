# CareNest wrap-up — 14 October 2026

## Release and completed work

Live: `carenest-00007-28h`, serving 100% traffic at
https://carenest-17055771987.asia-south1.run.app/ . The daily cleanup job now uses
that same image; this image update has not had a fresh cleanup execution.

- Backend computes remaining coverage with decimal arithmetic, policy-year and
  policy-linked claim checks. The browser displays the server result. It is an
  estimate from recorded claims, not a complete insurer balance.
- Reviewed bill rows retrieve selected-policy clauses and expose exact quotations,
  policy pages, bill pages and missing information. Related wording does not
  establish final payment eligibility. Stale evidence is invalidated.
- Follow-up context is server-side, guest-scoped and bounded to four turns. Policy
  or document changes reset usable history. Latest user clarifications are retained
  as unverified facts; earlier assistant text is not treated as evidence.
- Firestore uses `conversations/{session}/threads/{thread}` in addition to existing
  guest registry, session selection, cases, claim history and policy pages/clauses.
  Conversation records are included in guest cleanup.
- Angular 20 migration, compatible backend upgrades and pinned runtime constraints
  are complete. Latest dependency audits found zero known reported vulnerabilities;
  this is not an exhaustive security assessment.
- Backend suite: 129 tests pass. Frontend production build passes. Full synthetic
  release-v5 workflow passed 40 checks, including image bill ₹17,250, deterministic
  coverage, evidence, isolation and deletion. Reports are local/ignored.

## Answer quality: evidence and limits

The unchanged 12-question live benchmark improved from 8/12 expected verdicts
and 10/12 citation checks on v5 to 11/12 and 11/12 on v6. These are automated
contract/source checks, not a semantic accuracy score. One reference verdict
assumes pre-existing diabetes without sufficient onset facts. A dental answer
also attached an unrelated cataract/hernia quote: exact text alone does not prove
that the answer is supported.

A second model support check is implemented locally in `answer_support.py` and
fails closed when support cannot be established. It rejected the unrelated dental
example and accepted a supported room-limit example in real model checks. Unit
checks pass. This change is NOT in the live v7 deployment. Broader evaluation is
needed to measure false abstentions, latency and additional inference cost.

The v7 follow-up fix preserves supplied dates and instructs the answer to acknowledge
those facts. Its specific live date-clarification scenario still needs a fresh check.

## Fine-tuning experiment

The application still uses untuned Gemini 3.1 Flash-Lite with retrieval. Six policy
products supplied 124 training, 31 validation and 34 held-out ICICI examples, split
by policy. Labels are synthetic and machine-checked, not human-reviewed ground truth.
One epoch was submitted in us-central1. Estimated training-only cost: US$0.4157;
label generation, evaluation, storage and tax are excluded.

Job `projects/17055771987/locations/us-central1/tuningJobs/7122688972442042368`
was RUNNING at wrap-up. Do not submit a duplicate. The held-out baseline produced
34/34 parseable outputs and 33/34 exact-quote checks. All 26 policy-fact cases had
some verified citation; this does not prove every claim was supported. The tuned
arm has not run, and no improvement or promotion is claimed.

From the repository root, resume the existing job and comparison:

```sh
(cd backend && .venv/bin/python -m scripts.tune_policy_model ../training/drafts-v1 --region us-central1)
backend/.venv/bin/python eval/compare_tuned.py training/drafts-v1 eval/results/tuning-comparison.json --job-file training/drafts-v1/tuning-job.json
```

The comparison command requires a successful saved job. Review semantic accuracy,
unsupported statements, uncertainty, latency and cost before changing the live model.
The tuning output contract needs an adapter if the tuned model is promoted.

## Remaining work, in order

1. Run the full live question benchmark against the local semantic support check;
   inspect dental/implant evidence, false abstentions and latency, then deploy it.
2. Verify the deployed follow-up flow with a supplied diagnosis/onset date and a
   policy switch; confirm it retains relevant facts and drops obsolete context.
3. When the existing tuning job finishes, run the identical 34-case tuned arm,
   inspect both answers manually and decide whether to keep the retrieval baseline.
   Broaden human-reviewed, unseen-policy examples before making accuracy claims.
4. Verify the newly synchronized cleanup image once; inspect desktop/phone bill
   evidence UI and test several synthetic blurred/cropped image bills.
5. Before broader private-data use, inventory legacy unowned records and harden
   deletion during in-flight uploads/AI writes. Upgrade the Docker Node 20 build
   image to a supported LTS and rebuild. These are separate from hackathon evidence.

## New policy behaviour and prototype boundaries

A newly uploaded policy is privately ingested, split into page-linked clauses and
indexed for retrieval. Answers use that selected policy, not memorized wording from
training PDFs. A tuned model would improve response behaviour only if evaluation
supports it; retrieval remains necessary for unseen products and revisions.
Unreadable pages, missing schedules/riders or absent relevant evidence should lead
to clarification or inability to confirm. Bill evidence and coverage estimates do
not replace insurer adjudication. Policy recommendation remains a future feature.
