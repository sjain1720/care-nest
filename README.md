# CareNest

CareNest helps people understand health-insurance wording and investigate unexplained claim deductions. Nessi brings the policy, reviewed bill and insurer decision together, shows supporting pages, checks amounts in Python and prepares an editable clarification letter.

Built for **BFSI: Intelligent Risk, Fraud & Financial Experiences**, with a focus on transparent insurance interactions and informed financial decisions.

[Open CareNest](https://carenest-17055771987.asia-south1.run.app/)

## What works

- General insurance questions in Welcome, without borrowing fictional policy facts.
- A prepared fictional example with original Kotak Group Health Assure wording, two synthetic claims and clearly labelled fictional selections.
- Separate personal uploads, using the same policy and claim layouts without replacing the example workspace.
- Policy questions with original-page quotations, source checks and backend waiting-period calculations when the required evidence and dates are available.
- Reviewed bill extraction, amount reconciliation and related policy references. Unresolved references remain visible as needing clarification.
- Bounded ADK investigations that consult policy, bill and claim specialists, preserve unknown reasons and produce one explanation/checklist/letter.
- Editable letters with copy, text download and print/save-as-PDF actions. CareNest does not send them to insurers.

Policy PDFs use automatic native-text reading where conservative page checks pass, with Document AI imageless OCR fallback for other pages. Original page references and successful reading/indexing batches are preserved for retries. OCR quota errors receive bounded waits; sustained shared quota pressure can still require retry.

PDF policies are limited to **100 pages / 20 MB**. Supported document flows also accept photos; financial-image readability is checked before extraction. A readable image does not guarantee correct extraction: users review the rows and amounts.

## Try the example

1. Enter a display name/nickname. This personalizes the interface; it is not a sign-in or patient identity.
2. Open the fictional example. Its prepared data is attached to your own guest workspace without rerunning OCR/indexing.
3. Open **My policy**. Inspect the original wording and source-linked watch-outs. The ₹10 lakh cover and ₹2,500/day normal-room selection are fictional assumptions, not limits proven by the wording alone.
4. Open **My claim → Check my bill**. Compare the extracted values with the synthetic bill and save the review before investigation.
5. Ask Nessi:
   - `For cataract surgery on 2025-09-12, has my specified disease waiting period ended? What else needs confirmation?`
   - `Why was ₹20,000 deducted from my current claim? Examine each reason against my policy and tell me what evidence is missing.`
   - `Does the room-rent reduction apply to the implant too?`
   - `Who should I contact about the unexplained ₹4,800, and what exactly should I request?`
6. Expand the evidence, inspect the actual source pages, and edit the clarification letter. Fill its placeholders before any real-world use.

The real Kotak wording gives a **12-month specified-disease period on page 18** and lists cataract on page 19. With the example's fictional continuous-cover start of 12 March 2024, that period ends on 12 March 2025. This establishes timing only; medical history, member applicability, continuity, schedule terms and other conditions still matter.

The current fictional claim has ₹1,85,000 claimed and ₹1,65,000 approved: ₹20,000 deducted, comprising ₹9,100 room/associated charges, ₹6,100 implant and ₹4,800 with no stated reason. Matching a recorded calculation does not prove the deduction is justified. The previous separate fictional claim is ₹73,420. Recorded remaining cover is an incomplete-history estimate, not a live insurer balance.

## Why an application rather than a single PDF chat?

A PDF chat can explain wording. CareNest adds an owned, continuing workflow across the policy, reviewed bill and insurer decision:

- Original quotation checks and source-bound date arithmetic have separate, visible outcomes.
- Bill corrections feed backend reconciliation instead of relying on generated arithmetic.
- The bounded implant trace retains the bill row, explicit discount, original pages and calculation inputs.
- Missing facts, unexplained amounts, next actions and an editable letter stay connected to the selected claim.

This is the implemented differentiation, not evidence that CareNest outperforms every general PDF assistant. A fair direct-PDF comparison and broader user study remain open.

## Architecture

Angular 20 and FastAPI run in one Cloud Run container. Vertex AI provides Gemini and embeddings; Document AI reads documents; Firestore stores scoped state, original-page text and vectors; private Cloud Storage holds originals.

Normal questions use Python orchestration and Gemini where needed. Complex claim investigations use an ADK `claim_copilot` with `AgentTool` consultations to policy, bill and claim specialists. Backend code checks references, quotations, row association, arithmetic and stale inputs. The verifier is not a separate deployed agent service.

[Current architecture and diagrams](docs/CURRENT_ARCHITECTURE.md) · [Repository map](docs/REPO_MAP.md)

Configured source defaults: `gemini-3.1-flash-lite`, `text-embedding-005`, 768-dimensional vectors, Vertex global endpoint; document/storage services are configured for Mumbai. Configuration can override defaults. No active fine-tuned model, managed RAG Engine or insurer submission integration is claimed.

## Local development

Prerequisites: Python compatible with `backend/requirements.txt`, Node compatible with Angular 20, Google Cloud SDK, and access to a configured project. Dependencies are pinned; do not upgrade them merely to reproduce the demo.

```bash
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
cd frontend
npm ci
cd ..
gcloud auth application-default login
```

Update `backend/.env` for your own configured project, private bucket, Firestore database and Document AI processor. The example file and deployment/bootstrap scripts contain this prototype's project-specific settings; inspect them before using another project. Never commit credentials or `.env` files.

Start these in separate terminals:

```bash
bash scripts/dev-backend.sh
```

```bash
bash scripts/dev-frontend.sh
```

Open http://localhost:4200/. Angular proxies `/api` to the backend on port 8000. The example requires a prepared `demoTemplates` entry and original assets; a source checkout alone does not recreate ignored PDFs/cloud data. See `backend/scripts/prepare_example_workspace.py` and the current handoff before preparing it. Personal uploads require the configured cloud services too; this is not an offline application.

## Checks and deployment

```bash
cd backend
.venv/bin/python -m unittest discover -s tests -t .
```

```bash
cd frontend
NG_BUILD_MAX_WORKERS=2 npm run build
```

Synthetic/live review runners are under `eval/`; reports remain ignored. Backend tests mock external services and do not prove live model quality. Focused browser runners distinguish actual service captures from replayed UI checks.

After local acceptance, inspect project/service settings and deploy:

```bash
bash scripts/deploy.sh
```

The script uses Cloud Build/Cloud Run and updates the existing cleanup-job image when present. It can incur cloud usage. Do not rerun infrastructure bootstrap merely to update application code. `/api/health` is a service-health check; `/api/diag` actively calls cloud dependencies and is not a semantic correctness test.

## Privacy and prototype limits

- Guests have fixed seven-day identity expiry and a cleanup mechanism; no Google sign-in, account recovery or cross-device continuity is implemented. Display names are not authentication.
- Personal and example data have separate owned contexts. Workspace selectors do not grant access to arbitrary visitor identities.
- Original documents can contain sensitive information. Use public policies and synthetic financial/medical documents for demos; local masking is not comprehensive anonymization.
- Quota pressure can delay or interrupt indexing. Same-file progress/reuse is retained where valid; partially indexed policies are not activated. Increasing batch size does not increase API quota.
- AI support review can fail or be mistaken. A matching quote or elapsed waiting period does not establish coverage, payment or guaranteed recovery.
- Broader deduction provenance, consequential clarification, simultaneous cold-upload testing and full journey cost/latency remain open. The reviewed example claim/letter was accepted, and one three-visitor prepared-example request exercise passed. These do not establish broad accuracy or production scalability.

## Release and evidence status — 18 October 2026

Deployed release: **`carenest-00027-g6s`**, serving 100% of traffic in Mumbai. It includes the nine-step claim journey, attachment progress/highlighting, personal sample-policy guard, source-backed policy answers, hospital-insurance guide, automatic native-text reading and imageless OCR fallback with bounded quota recovery.

Verification: **315 backend tests passed**, production frontend build passed, and a hosted three-page mixed native/OCR PDF uploaded successfully with its original file hash preserved. Re-upload reused the completed result; the disposable test session was deleted. The reviewed fictional cataract answer, implant finding, unexplained deduction and clarification letter were accepted separately. These checks are not an accuracy percentage or a production-scale benchmark.

For a short demonstration, use the prepared fictional claim: show the ₹20,000 difference, investigate once, inspect the original policy exception and unknown ₹4,800, then review the editable clarification letter. Keep policy selections labelled fictional and record external sending only after the user actually sends a response. Rehearse the exact hosted path before recording.

Some supporting documents and original demo assets are local/ignored and may not be present in a published source checkout. Include approved documentation/assets explicitly when assembling a reproducible submission; never publish credentials or patient records.
