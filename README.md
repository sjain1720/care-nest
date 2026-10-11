# CareNest – Policy Pre-Mortem

An AI health-insurance companion: reads the user's own policy and helps before, during and after a hospital stay.
Single Cloud Run service: Angular UI + FastAPI API (`/api/*`) in one container.

| Setting | Value |
|---|---|
| GCP project | `project-796a7c44-1092-4e43-ba6` |
| Region (Cloud Run, Firestore, bucket, Document AI) | `asia-south1` |
| Gemini location | `global` (Vertex AI, no API key) |
| Document AI | OCR processor `771975839b0e4376`, PDFs only, max 60 pages, 15 pages per request |
| Bucket | `gs://project-796a7c44-1092-4e43-ba6-docs` |

## Folder layout

```
backend/
  app/main.py            API routes + serves the Angular build
  app/core/config.py     settings from backend/.env (or Cloud Run env vars)
  app/core/gcp.py        Gemini, Document AI, Firestore, Storage clients
  app/services/ocr.py    splits PDFs into 15-page pieces and runs OCR, keeping real page numbers
  app/routers/health.py  /api/health and /api/diag (calls every Google service once)
  agents/hello_agent/    ADK test agent on Vertex AI
  scripts/smoke_test.py  Phase 0 connection test
frontend/                Angular 19 + Material 3 app (Phase 1 screens on mock data; /status = service check)
  public/mocks/          demo-case JSON that follows src/app/models/models.ts (the API contract)
  src/app/services/api.service.ts   USE_MOCKS switch: mocks now, /api/* later
infra/gcp-bootstrap.sh   one-time GCP setup (run in Cloud Shell)
scripts/                 Bash helpers for Cloud Shell: setup, dev, smoke test, deploy
demo-data/  eval/
```

## Phase 0 setup (Google Cloud Shell)

Everything runs in [Cloud Shell](https://shell.cloud.google.com): gcloud, Python, Node and Git are preinstalled and you are already signed in.

1. **Get the code into Cloud Shell**: clone the repo (`git clone <repo-url> carenest`), or zip this folder and use *More (⋮) > Upload*, then `unzip carenest.zip`.
2. `cd carenest && sed -i 's/\r$//' scripts/*.sh infra/*.sh` (strips Windows line endings, harmless otherwise).
3. **One-time GCP setup**: `bash infra/gcp-bootstrap.sh`
   Creates the `ppm-runner` service account + roles, the Firestore vector index, and clears bucket soft-delete.
4. **Setup**: `bash scripts/setup.sh` (venv, pip, npm). Create `backend/.env` from `.env.example` if it was not uploaded.
5. **Connection test**: `bash scripts/smoke-test.sh demo-data/sample_policy.pdf`
6. **Run** (two Cloud Shell tabs): `bash scripts/dev-backend.sh` and `bash scripts/dev-frontend.sh`, then *Web Preview > Change port > 4200* and click *Check Google services*.
7. **ADK test agent**: `bash scripts/adk-web.sh` (stop the backend first; both use port 8000), then *Web Preview* on port 8000.
8. **Deploy**: `bash scripts/deploy.sh`, then open `<url>/api/diag`.

Cloud Shell limits: about 50 hours/week; the session stops after inactivity, but `$HOME` (5 GB) is kept.

## Phase 0 done when

- [ ] Smoke test passes (Gemini, embeddings, Firestore, Storage, OCR with correct page numbers)
- [ ] Web Preview (port 4200) shows backend `ok` and all services OK
- [ ] `adk web` agent answers using Vertex AI
- [ ] Cloud Run URL loads the UI; `/api/diag` reports `all_ok: true`
- [ ] Budget alert ($25) set; Artifact Registry cleanup policy added
- [ ] Demo files uploaded; golden questions filled in

## Rules

- Never commit `backend/.env` or any key file. Credentials come from your Cloud Shell sign-in and the `ppm-runner` service account on Cloud Run.
- Synthetic or public documents only – no real patient data.
