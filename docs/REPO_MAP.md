# CareNest repository map

Read this file first; use the matching row to narrow searches. Paths are relative
to the repository root. For symbol and endpoint lookup:

```sh
python3 scripts/repo-map.py --query waiting
python3 scripts/repo-map.py --query session --details
python3 scripts/repo-map.py --query /copilot
```

The lookup scans source declarations only, excludes secrets/datasets/builds, and
prints a bounded result. It costs no model/API credits. The map reduces discovery
context; exact token savings depend on each task.

## Entry points and contracts

| Area | Start here | Follow when needed |
|---|---|---|
| Backend startup / SPA | `backend/app/main.py` | `backend/app/routers/`, `Dockerfile` |
| API shapes | `backend/app/schemas.py` | `frontend/src/app/models/models.ts` |
| Frontend startup / routes | `frontend/src/app/app.config.ts`, `app.routes.ts` | `app.component.ts/html/css` |
| UI API / mock switch | `frontend/src/app/services/api.service.ts` | `sse.ts`, `frontend/public/mocks/` |
| Cloud clients / config | `backend/app/core/gcp.py`, `config.py` | `.env.example`, `scripts/deploy.sh` |
| Work queue / current evidence | `docs/DEVELOPMENT_QUEUE.md` | `AI_QUALITY_REPORT.md`; `GPT_6_1_SOL_HANDOFF.md` (historical review) |

## Feature-to-file lookup

Backend service paths below are under `backend/app/services/`; frontend pages are
under `frontend/src/app/pages/`; tests are under `backend/tests/`.

| Feature | Backend router → services | Frontend | Relevant tests |
|---|---|---|---|
| Guest identity, retention, delete | `core/session*.py`, `routers/session.py` → `session_registry.py`, `data_lifecycle.py`, `policy_store.py`, `case_store.py` | `app.config.ts`, `pages/status/` | `test_guest_session.py`, `test_session_security.py` |
| Upload / OCR / types | `routers/policy.py` → `policy_ingest.py`, `case_ingest.py`, `ocr.py`, `file_types.py`, `doc_extract.py` | `upload/` | `test_upload_and_routing.py`, `test_bill_and_case.py` |
| Policy extraction / schedule | `routers/policy.py` → `policy_extract.py`, `policy_details.py`, `clauses.py`, `embeddings.py`, `policy_store.py` | `policy/`, `policy-details-form.component.ts` | `test_policy_logic.py`, `test_policy_details.py` |
| Chat routing and grounded QA | `routers/copilot.py` → `copilot.py`, `intents.py`, `policy_qa.py`, `case_qa.py`, `general_qa.py`, `grounding.py`, `conversation.py`, `answer_support.py`, `plain_language.py`, `steps.py` | `ask/`, `services/chat.service.ts`, `shared/chat-*`, `answer-card.component.ts` | `test_live_findings.py`, `test_merge_integration.py`, `test_ai_workflows.py` |
| Bill review / amounts | `routers/case.py` → `bill_review.py`, `bill_checks.py`, `bill_policy.py`, `case_builder.py` | `bill-check/`, `bill-review.component.ts` | `test_bill_review.py`, `test_bill_and_case.py`, `test_ai_workflows.py` |
| Settlement / rejection | `routers/case.py` → `settlement_checks.py`, `deduction_explainer.py` | `settlement/`, `shared/waterfall.component.ts` | `test_phase5.py`, `test_copilot_and_letters.py` |
| Drafts / query / insurer replies | `routers/case.py` → `letter_writer.py`, `letters.py`, `query_help.py`, `reply_reader.py` | `letter/`, `query-helper/`, `reply/` | `test_copilot_and_letters.py`, `test_phase5.py` |
| Claim history / diary | `routers/claims.py`, `routers/case.py` → `claim_history.py`, `claim_tracker.py`, `case_store.py` | `case/`, `services/journey.service.ts`, `shared/claim-diary.ts` | `test_claim_history.py`, `test_claim_diary.py` |
| Remaining cover estimate | `routers/coverage.py` → `coverage.py`, `claim_history.py` | `shared/coverage-estimate.component.ts` (server result) | `test_coverage.py` |
| Citation PDF viewer | `routers/policy.py`, `routers/case.py` | `services/citation-viewer.service.ts`, `shared/citation-*` | QA grounding and guest isolation tests |
| Health / demo | `routers/health.py`, `routers/demo.py` → `connectivity.py`, `demo_loader.py` | `status/`, `home/` | `scripts/smoke_test.py`; real-cloud E2E checks |
| Styling / Hindi / navigation | — | `frontend/src/styles.css`, `shared/translate.pipe.ts`, `services/theme.service.ts`, `settings.service.ts` | production build + browser checks |

## Workflows

```text
Upload → detect type → policy_ingest or case_ingest → OCR → structured extraction
       → private Storage + Firestore → review fields → deterministic checks
Question → session context → copilot intent → general / policy / case answer
         → policy embeddings retrieval → Gemini → quote verification → SSE/UI
Draft → selected guest case + policy → letters facts → Gemini wording
      → amount/header validation → editable UI draft
```

The normal chat endpoint is `/api/copilot/ask[/stream]`. The separate
`/api/copilot/agent` uses `backend/app/adk_copilot.py` and `agent_tools.py`;
do not confuse its experimental free-text output with verified answer cards.

## Storage and cloud

`core/gcp.py` creates clients lazily. Runtime: Cloud Run monolith; Firestore and
private Storage/OCR in Mumbai; Gemini/embeddings use the approved global endpoint.
Policy pages/clauses include page provenance and 768-dimensional vectors.
`trainingPolicies` is a separate corpus, not automatically the active user policy.
Refer to the lifecycle implementation for current ownership and retention paths.

## Offline training and evaluation

| Need | Files |
|---|---|
| Extract selected PDFs / corpus | `backend/scripts/prepare_policy_corpus.py` |
| Index / check five-policy corpus | `backend/scripts/index_policy_corpus.py`, `check_policy_corpus.py` |
| Generate/review synthetic examples | `backend/scripts/draft_tuning_data.py`, `training/README.md` |
| Cost preflight / optional tuning job | `backend/scripts/tune_policy_model.py` |
| QA evaluations | `eval/evaluate_live.py`, `eval/run_policy_eval.py`, `eval/compare_tuned.py` |
| Bill / dataset checks | `eval/run_bill_check.py`, `run_dataset_check.py` |
| Synthetic source assets | `demo-data/make_demo_pdfs.py`, `frontend/public/demo/` |

Generated `training/*`, `eval/results/*`, actual PDF corpus, environments and
credentials are ignored. Do not read them for routine UI changes.

## Deployment and verification

`Dockerfile`: Angular build → Python image → same-origin UI/API.
`scripts/deploy.sh`: source build and Cloud Run deployment.
`infra/gcp-bootstrap.sh`: one-time infrastructure; inspect before re-running.
`infra/artifact-cleanup.json`: build-image retention.
`infra/configure-guest-cleanup.sh`: daily `app.cleanup` Cloud Run job and Scheduler.
`scripts/verify-release.py`: repeatable synthetic real-cloud smoke flow.
`backend/tests/`: fast unit/integration suite with mocked external services.
Passing this suite alone does not demonstrate live OCR, Gemini or isolation.

Runtime dependencies are pinned in `backend/requirements.txt` and `constraints.txt`;
frontend versions are locked in `frontend/package-lock.json`. Angular uses the
application builder (`@angular/build`), not the legacy webpack bundle.
Tuning comparison: `eval/compare_tuned.py`; reports and generated labels stay ignored.
