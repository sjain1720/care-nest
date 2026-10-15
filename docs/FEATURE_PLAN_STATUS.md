# CareNest feature plan status

Reviewed 14 October 2026 against `1. CareNest_ feature list.docx`,
`MONOLITH PLAN.html`, the UI implementation plan and current source code.
The documents describe requested behaviour; code existence does not establish
answer accuracy or complete acceptance. Cloud evidence is in `AI_QUALITY_REPORT.md`.

## Original five features

| Feature | Implemented path | What is still incomplete |
|---|---|---|
| Personal policy explainer | Policy upload, structured extraction, schedule correction, semantic retrieval, source/page Q&A | Broader semantic answer validation; reliable missing-page/version checks; dependent eligibility and ambiguous wording review |
| Hospital bill and coverage analyzer | Image/PDF extraction, editable rows, deterministic totals/room checks, reviewed row-to-clause evidence, server coverage estimate | More image-quality cases; policy-specific payable/out-of-pocket estimates including rider, co-pay and deductible applicability. Row evidence currently shows related clauses rather than final coverage |
| Claim preparation assistant | Collected/missing checklist, document sources, cover letters, editable drafts and claim diary | `case_builder.py` starts with a generic reimbursement list. Cashless versus reimbursement requirements and verified policy/insurer/request-specific checklist generation are incomplete |
| Rejection and deduction assistant | Settlement arithmetic and waterfall, stated reasons, clause retrieval, clarification/reconsideration/grievance drafts, evidence index and escalation links | Each deduction needs semantic support verification. Current trust calculation can mark supporting amount or quotation as sufficient without proving applicability. Rejection checklist is largely generic. Official deadline verification remains incomplete |
| Waiting-period and PED tracker | Extracted initial/specific/PED periods, backend date calculations, policy display and chat clarifications | Continuity/portability/endorsement applicability needs qualified evidence. Follow-up storage/isolation was verified; some answers safely abstain. Automatic scheduled notifications are not implemented |

The unified Claim Copilot provides routing and linked next steps across these
features. It is not yet the fully evidenced deduction action plan described by the
mother's ₹38,000 example. Relevant example documents are needed to verify that
specific reconstruction; fabricated policy or medical evidence must not fill gaps.

## Build phases and architecture

- Phase 0, monolith/cloud foundation: deployed Angular/FastAPI, Firestore, private
  Storage and Document AI in Mumbai; approved global Gemini/embeddings inference.
- Phase 1, UI shell: working routes, Material components, demo/live indicators,
  upload/chat/checklist. Explicit first-visit choices, clean demo reset/mode switching
  and final phone acceptance are still partial.
- Phase 2, ingestion/retrieval: implemented with Document AI OCR and Firestore
  vectors, rather than the proposed Layout Parser plus managed Vertex RAG Engine.
  Readable policy text and page provenance are retained. Bill images currently use
  Gemini directly; do not claim every image passes through Document AI.
- Phase 3, bill/reconciliation: implemented deterministic totals, room calculations,
  settlement differences and bill evidence. Individual rule applicability still
  needs source validation before describing estimates as insurer-payable amounts.
- Phase 4, orchestration/appeal: normal chat uses Python routing, structured Gemini
  outputs and quote checks. ADK exists behind an experimental endpoint; it is not
  the verified default workflow. A semantic support guard is now deployed for policy QA.
- Phase 5, integration/polish: SSE, source-page viewer, waterfall and responsive
  pages exist. Full phone/device walkthrough and precisely localized Hindi output
  remain verification work; source-text highlighting is not established for all PDFs.
- Phase 6, evaluation/rehearsal: custom synthetic cloud smoke and question evaluation
  exist. The proposed 55-question managed Vertex evaluation and backup judging video
  have not been completed. Exact citation checks are not a semantic accuracy score.

Other differences: the feature DOCX specifies Angular, which matches the repository;
the later UI plan's React suggestion has not been adopted. Retention is seven days
with explicit graph cleanup, rather than the UI plan's illustrative 24-hour/TTL
proposal. Managed context caching and Cloud DLP are not implemented; local PII
masking is not equivalent to Cloud DLP. The monolith plan's US$17.22 figure is an
estimate for a different proposed workload, not evidence of actual project spend.

## Execution order

1. Existing answer-support benchmark and six follow-up storage/isolation checks completed; broader semantic quality still needs review.
2. Tuning comparison completed on 34 identical held-out inputs. Keep the baseline; broaden semantic evaluation before promotion.
3. Complete the next product workflow selected by the user: personalized claim
   checklist, or stronger deduction evidence/action plan. The user confirmed completing the existing five-feature workflow first.
4. Verify the full prototype on phone and desktop; prepare the judging run/video.
5. Before broader private use, handle legacy ownership and in-flight deletion races.

User-confirmed after-hackathon list: policy recommendation,
automatic alerts, accounts/family profiles, insurer integration and complete benefit
accounting. The original feature DOCX itself does not mark deferred features.
