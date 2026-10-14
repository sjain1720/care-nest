# CareNest tuning comparison

Completed 14 October 2026. The existing Gemini 3.1 Flash-Lite tuning job succeeded;
no second job was submitted. The app still uses the untuned retrieval baseline.

## Experiment and results

One epoch used 124 synthetic training examples and 31 validation examples. Test
records were held out by policy: 34 examples from ICICI Criti Shield Plus, a benefit
product. Both arms received identical question/evidence inputs and output instructions.
The comparison tests explanation given evidence; it does not test retrieval recall.
Training labels and references were machine-checked, not human-reviewed ground truth.

| Automated check | Baseline | Tuned |
|---|---|---|
| Parseable structured outputs | 34/34 | 34/34 |
| Every emitted quote matches its supplied page text | 33/34 | 34/34 |
| Policy-fact cases with at least one valid citation | 26/26 | 26/26 |
| Missing-information cases with a limitation field | 6/6 | 6/6 |
| Raw approval-wording heuristic passes | 34/34 | 33/34 |

The last row is a lexical flag, not an established approval promise. Inspection
found the flagged tuned answer says it **cannot confirm** guaranteed approval and
cannot provide guarantees. It is a refusal. Keep the raw flag visible rather than
claiming the metric is a reliable safety score.

The baseline's invalid quote was a stitched/non-contiguous quote in the question
about adding a 20-year-old son. The tuned answer used exact quotes and retained the
financial-dependence qualification. Both arms distinguished a Loss of Pay add-on's
contract-employee eligibility from general enrollment, declined to invent claim
status/premium/schedule details, and refused treatment advice in the emergency example.
This qualitative inspection is not an independent clinical/insurance expert review.

## Decision

Keep the retrieval baseline in the live app for now. One corrected quotation on
34 synthetic questions is insufficient evidence of a broad accuracy improvement.
The held-out set covers one product and mostly definition/benefit questions; it
lacks enough realistic multi-document claims, adversarial inputs and varied insurers.
The current comparison also did not record per-call latency or usage, so it cannot
establish a speed or inference-cost advantage.

The trained endpoint is available for a future controlled integration. Its output
shape differs from the app's answer-card contract; promotion requires an adapter,
source verification and the same uncertainty/safety rules. Newly uploaded policies
must still be ingested and retrieved, regardless of the serving model.

## Next evidence to collect

- Independently review a small, varied set of policy questions and actual supplied
  clauses, with onset/schedule/rider facts and explicit unknowns.
- Add bill/settlement discrepancies, irrelevant clauses, prompt injection and
  incomplete evidence cases. Compare identical retrieval outputs for both arms.
- Record latency and token usage in future runs rather than repeating completed
  predictions only to reconstruct missing telemetry.
- Re-evaluate with the app's real answer-card/source-verification path before promotion.

Generated labels, model endpoint metadata and detailed outputs remain ignored at
`training/drafts-v1/` and `eval/results/tuning-comparison.json`.
