# CareNest current architecture

Verified against source on 14 October 2026. Live revision `carenest-00008-7wp`
serves the untuned Gemini 3.1 Flash-Lite workflow, including policy answer support
checking. The default app uses Python orchestration. ADK is a separate experimental
endpoint and is not called by the Angular chat service.

## Deployed application

```mermaid
flowchart TB
    User["Visitor: guest or fictional demo"] --> UI["Angular 20 UI\nUploads, chat, citations, bill review, letters"]
    subgraph Run["One Cloud Run monolith · Mumbai"]
        UI --> API["FastAPI /api\nIssued guest cookie, ownership and expiry checks"]
        API --> Upload["Document ingestion\nClassify, extract, preserve page provenance"]
        API --> Context["Bounded follow-up context\nGuest + thread + policy/document scope"]
        Context --> Router["Python Claim Copilot\nGemini intent router + keyword fallback"]
        Router --> Policy["Policy QA service"]
        Router --> Case["Bill, settlement and checklist QA services"]
        Router --> General["General insurance QA"]
        Router --> Balance["Deterministic coverage calculator"]
        Policy --> Retrieve["Selected-policy clause retrieval"]
        Policy --> Verify["Exact quote check + model support review\nAbstain when unsupported"]
        API --> Evidence["Reviewed bill-row evidence mapping"]
        Evidence --> Retrieve
        Evidence --> RowCheck["Exact row citation checks\nRelated wording, not approval"]
        API --> Draft["Claim / clarification / appeal drafts\nValidated facts + amount checks; editable"]
        Upload --> Checks["Deterministic totals, dates, room checks\nSettlement reconciliation"]
        Verify --> API
        RowCheck --> API
        Balance --> API
    end
    Upload --> OCR["Document AI OCR · Mumbai\nPolicy/document PDFs; page-batched"]
    Upload --> Vertex["Vertex AI · approved global inference\nGemini 3.1 Flash-Lite + text-embedding-005\nExplicit bill images use Gemini"]
    Router --> Vertex
    Policy --> Vertex
    Case --> Vertex
    General --> Vertex
    Evidence --> Vertex
    Draft --> Vertex
    Verify --> Vertex
    Retrieve --> FS["Firestore · Mumbai\nGuests, selected policies, page clauses/vectors\nCases, claim history, conversation threads"]
    API --> FS
    Upload --> GCS["Private Cloud Storage · Mumbai\nOriginal policy and claim documents"]
    Scheduler["Cloud Scheduler\nDaily 03:00 India time"] --> Cleanup["Cloud Run cleanup job\nExpired/revoked guest graph deletion"]
    Cleanup --> FS
    Cleanup --> GCS
    API -. "Experimental endpoint only" .-> ADK["POST /api/copilot/agent\nADK root + 3 specialist agents"]
    ADK -. "Shared application tools" .-> Retrieve
    ADK -. "Shared application tools" .-> Checks
```

Chat streams progress and an answer card through `/api/copilot/ask/stream`; JSON
clients use `/api/copilot/ask`. Labels such as “Policy Specialist” and “Verifier”
in this default path are service/progress labels, not evidence of an ADK transfer.

The semantic support guard currently applies to **policy QA**. Case answers and
bill-row evidence have their own source/quote checks; do not describe every output
as having passed the new semantic guard. Arithmetic remains backend code.
Firestore vector retrieval is custom RAG. Managed Vertex RAG Engine, Vertex context
caching and Cloud DLP are not wired into this path. Originals are private but can
contain PII; local text masking is not comprehensive de-identification.

## What ADK actually contains

```mermaid
flowchart TB
    Experimental["Experimental /api/copilot/agent\nNot called by normal Angular chat"] --> Runner["ADK Runner\nFresh in-memory session per question"]
    Runner --> Root["claim_copilot\nGemini chooses specialist transfer"]
    Root --> PS["policy_specialist"]
    Root --> BA["bill_analyst"]
    Root --> CA["claim_assistant"]
    PS --> PT["search_policy\nwaiting_period_status\npolicy_summary"]
    BA --> BT["bill_check_summary\nsettlement_breakdown\nsearch_policy"]
    CA --> CT["document_checklist\nescalation_steps"]
    PT --> Shared["Shared app data/services\nGuest-scoped policy and case access"]
    BT --> Shared
    CT --> Shared
    Runner --> Output["Free text + tool/transfer steps\nNo normal AnswerCard verifier pipeline"]
```

This is real ADK agent configuration, but the original diagram's complete agent
architecture has not been made the default. There is no separate ADK rejection
specialist or ADK self-checking verifier. `bill_analyst` handles settlement/rejection
questions, and the robust policy verifier belongs to the Python answer-card path.
ADK uses `InMemorySessionService`, a fixed internal user label `demo` and a new
session per request; it does not implement the normal guest-scoped follow-up threads.
Its live correctness/transfer/isolation acceptance has not been established here.

## Training and release path

```mermaid
flowchart LR
    PDFs["Public policy corpus"] --> Labels["Synthetic machine-checked examples\n124 train / 31 validation / 34 held-out"]
    Labels --> Tune["Vertex supervised tuning · us-central1\nOne completed epoch"]
    Tune --> Candidate["Tuned candidate endpoint\nNot enabled in app"]
    Candidate --> Compare["Identical held-out evidence comparison"]
    Baseline["Untuned Gemini 3.1 Flash-Lite"] --> Compare
    Compare --> Decision["Keep baseline for now\nBroader semantic review needed"]
    Repo["Repository"] --> Build["Cloud Build + Artifact Registry\nNode 24 frontend build / Python runtime"]
    Build --> Deploy["Cloud Run monolith"]
```

The tuning comparison produced baseline 33/34 and tuned 34/34 exact-quote checks;
it does not establish broad insurance accuracy or end-to-end superiority. A new
policy is ingested and retrieved in either design; it does not need retraining.
See `TUNING_COMPARISON.md` for limitations and the promotion decision.

## Source navigation

- Frontend entry: `frontend/src/app/services/api.service.ts` (streaming chat).
- Normal routing: `backend/app/routers/copilot.py`, `services/copilot.py`.
- Follow-ups and policy checks: `services/conversation.py`, `policy_qa.py`, `answer_support.py`.
- Bill evidence: `services/bill_policy.py`; calculations: `coverage.py`, `bill_checks.py`, `settlement_checks.py`.
- ADK team/tool wrappers: `backend/app/adk_copilot.py`, `agent_tools.py`.
- Clients, regions and lifecycle: `backend/app/core/gcp.py`, `config.py`, `app/cleanup.py`.
- Source deploy/build: `scripts/deploy.sh`, `Dockerfile`; cleanup schedule: `infra/configure-guest-cleanup.sh`.
