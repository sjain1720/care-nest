# CareNest policy training preparation

Latest checkpoint: `drafts-v1/` contains 99 accepted synthetic, machine-checked examples across three completed policies: 65 train / 0 validation / 34 test. Navi and Star preparation is incomplete and was stopped at the user's request to wind up. Larger Flash generated the drafts; later audit batches used Flash-Lite. The labels are not human-reviewed ground truth. No tuning job has been submitted. `scripts/tune_policy_model.py` requires at least 100 train examples plus validation/test splits and checks an estimated US$5 ceiling before optional submission. See `PROJECT_STATUS.md` for the current runtime and next steps.

The five PDFs selected by the user contain 271 pages of extractable text. `policy-corpus/manifest.json` records SHA-256 checksums, page counts and extraction review flags. `pages.jsonl` preserves PDF page numbers; `clauses.jsonl` contains 811 bounded passages. Clause labels are heuristic, so review them against the PDF before treating them as authoritative section labels. Non-empty extracted text does not prove table reading order or complete fidelity.

Regenerate locally:

```bash
cd backend
.venv/bin/python -m scripts.prepare_policy_corpus ../policies-data-set ../training/policy-corpus
```

Index the evidence in the private project:

```bash
cd backend
.venv/bin/python -m scripts.index_policy_corpus ../training/policy-corpus ../policies-data-set
```

The indexing script uses `trainingPolicies/<policyId>/pages` and `/clauses`, and the private bucket prefix `training/policies/`. It reuses completed matching policies and does not change `app/state` or the demo case. These are retrieval records, not trained weights and not fully extracted app policy facts.

All five selected policies indexed successfully on 13 October 2026. Stored PDF checksums, page/passage counts and nearest-neighbour retrieval checks passed for each. To repeat those checks:

```bash
cd backend
.venv/bin/python -m scripts.check_policy_corpus ../training/policy-corpus
```

## Supervised tuning target

`annotation_queue.jsonl` provides 100 initial questions (20 per selected policy) and keyword-selected candidate passages. Answers are deliberately empty, review status is pending, and splits are unassigned. Candidate passages can omit exceptions or context; verify the complete relevant PDF sections before labelling. This queue is not a valid tuning dataset and must not be submitted to Vertex as-is.

Input: a user's question plus retrieved policy passages with policy ID, PDF page and clause metadata. Output: a grounded answer, coverage limitations, unknown or missing schedule details, and verified evidence references. Train behaviour on supplied evidence rather than memorising particular insurance products.

Start by comparing the existing untuned model with retrieval against a held-out policy. Prepare 100–500 carefully reviewed examples across coverage, waiting periods, co-payment, room restrictions, exclusions, claim documents and ambiguity. Include negative examples where the supplied evidence cannot answer the question. Public wordings often do not establish an individual's sum insured, start date, continuity or selected benefits; training answers must not invent these values.

Suggested annotation record (internal format, not a Vertex upload schema):

```json
{
  "policyId": "source policy ID",
  "question": "user question",
  "evidence": [{"page": 1, "quote": "exact extracted source text"}],
  "answer": "human-verified answer with limitations",
  "reviewStatus": "approved",
  "reviewer": "reviewer identifier",
  "split": "train"
}
```

Split by entire policy/product, not random passages: for an initial experiment, use three selected PDFs for training, one for validation, and one for a held-out test. Confirm insurer/product identities and revisions before assigning these splits; related wordings must not leak across them. More independent products from the remaining folder can broaden the test set. The existing demo's 12 golden questions remain separate.

Before a job: validate exact evidence matches and page numbers, review answers for factual correctness, confirm supported tuning model and regional job location, estimate training tokens multiplied by epochs, and establish the retrieval baseline. Global inference approval does not establish support for a global tuning job; tuning uses a supported regional endpoint. Export reviewed records into the currently documented Vertex tuning schema. Corpus preparation does not launch training. The tuning script launches a job only with `--submit`; an existing saved job is resumed without resubmission.

After a job: compare tuned and untuned models on identical held-out retrieval inputs for answer accuracy, citation correctness, unsupported-claim rate, and missing-information handling. Use measured scores in the hackathon presentation.

Official guidance: https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/tuning/supervised-tuning/use

## 14 October experiment update

Six policies now contribute synthetic, machine-checked drafts: 124 training, 31
validation (Navi), 34 held-out tests (ICICI). Bajaj supplements the training split.
Teacher provenance is per example; older drafts used 3.5 Flash, newer drafts
used 3.1 Flash-Lite. These are not human-verified ground truth.

One epoch of Gemini 3.1 Flash-Lite was submitted in us-central1; token counting
uses the working global inference endpoint. Preflight: 138,562 tokens including
JSON overhead, approximately US$0.4157 training only. Job metadata, label files
and reports are ignored/local. The live app still uses the untuned model.

Comparison runner: `eval/compare_tuned.py` uses identical ICICI evidence for
both models, minimal thinking and the same output contract. The baseline has
34/34 parseable JSON outputs and 33/34 exact-quote checks; all 26 policy-fact
examples have some verified citation. These checks do not establish semantic
insurance accuracy. Run the tuned arm only after the saved job succeeds.
