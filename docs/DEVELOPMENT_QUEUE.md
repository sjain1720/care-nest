# CareNest development queue — 14 October 2026

Read `REPO_MAP.md` for navigation and `AI_QUALITY_REPORT.md` for release evidence,
limitations and exact resume commands. Older handoff documents are historical.

## Completed

Repository navigation; issued guest identity and isolation; retention/deletion;
synthetic live demo; deterministic backend coverage; reviewed bill-row policy
citations; bounded server-side follow-up context; Angular/backend dependency fixes;
quality evaluation harness and held-out tuning comparison runner.

Live revision: `carenest-00007-28h`. Cleanup image synchronized with that revision.
129 backend tests and production frontend build pass. Full cloud workflow passed
40 checks on v5; the 12-question benchmark reached 11/12 verdict and 11/12 citation
checks on v6. These reports are not semantic insurance accuracy scores.

## Next tasks, in order

1. Evaluate the local answer-support guard broadly, inspect unsupported dental
   evidence and false abstentions, measure latency, then deploy. It is not live yet.
2. Recheck the v7 diagnosis/onset-date follow-up and policy-switch scenarios live.
3. Resume the existing running tuning job; compare both arms on the same 34 held-out
   examples, review answers and decide whether promotion is justified. No tuned
   model is enabled in the application. Do not launch a duplicate job.
4. Execute the updated cleanup worker once; inspect bill evidence on desktop/phone
   and test blurred/cropped synthetic bill images.
5. Before private multiuser use: legacy record inventory and in-flight deletion
   hardening. Upgrade the Docker Node build image to supported LTS and rebuild.

## Prototype verification strategy

Keep fast tests for arithmetic, evidence integrity, routing and guest isolation.
They use mocks and do not establish real model quality. Run the cloud workflow
once after a meaningful release, rather than after every styling edit:

```sh
backend/.venv/bin/python scripts/verify-release.py --url https://carenest-17055771987.asia-south1.run.app --full --bill-image /private/tmp/carenest-release-bill.png
```

Reports/training data stay ignored. Machine-checked labels need human review.
The application continues to retrieve from a newly uploaded policy; fine-tuning
is not a replacement for ingestion, relevant source evidence or missing facts.
