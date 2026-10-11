# CareNest – Local Setup Guide

How a new team member sets up CareNest on their own computer.
This file is updated after every phase. Each phase section lists only what that phase **adds**, so follow the sections in order.

| Phase | What you can run locally after it |
|---|---|
| Phase 0 – Foundation | Backend (FastAPI) talking to Google Cloud, plus the connection test |
| Phase 1 – UI/UX shell | The full web app on demo data (no Google Cloud needed) |

> **Company laptops:** if your network inspects HTTPS traffic, the gcloud CLI may fail with `CERTIFICATE_VERIFY_FAILED`. In that case:
> - Run the **frontend** locally: npm works on these networks.
> - Run anything that needs Google Cloud in [Cloud Shell](https://shell.cloud.google.com), using the same commands in their Linux form.
>
> Don't turn off SSL checks to get around this.

---

## Phase 0 – Foundation

### 1. Install the tools (once per computer)

| Tool | Version | Check | Needed for |
|---|---|---|---|
| Git | any recent | `git --version` | Getting the code |
| Python | 3.12 | `python --version` (Windows: `py -3.12 --version`) | Backend |
| Node.js | 22 LTS recommended (24 also worked in our test) | `node -v` | Frontend |
| Google Cloud CLI | latest | `gcloud --version` | Backend calls to Google Cloud |

**Windows (winget):**
```powershell
winget install --id Git.Git --exact
winget install --id Python.Python.3.12 --exact --scope user
winget install --id OpenJS.NodeJS.LTS --exact
winget install --id Google.CloudSDK --exact
```
Close and reopen the terminal afterwards so the new tools are found.

**macOS (Homebrew):**
```bash
brew install git python@3.12 node@22
brew install --cask google-cloud-sdk
```

**Linux / Cloud Shell:** Cloud Shell already has all four. On other Linux machines, use your package manager plus Google's [gcloud install guide](https://cloud.google.com/sdk/docs/install).

### 2. Get the code
```bash
git clone <repo-url> carenest
cd carenest
```

### 3. Sign in to Google Cloud (no key files)
Ask the project owner to add your Google account to project `project-796a7c44-1092-4e43-ba6` (Editor role is enough for the hackathon). Then:
```bash
gcloud auth login
gcloud config set project project-796a7c44-1092-4e43-ba6
gcloud auth application-default login
gcloud auth application-default set-quota-project project-796a7c44-1092-4e43-ba6
```
The `application-default` login is what the Python code uses. Never download or commit service-account key files.

### 4. Backend: Python environment and settings
**Windows (PowerShell):**
```powershell
cd backend
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
```
**macOS / Linux / Cloud Shell:**
```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```
`backend/.env` already contains the project, bucket, Document AI processor and region values. It is excluded from Git, so don't commit it.

### 5. Connection test
Run from `backend/`. Passing a policy PDF also tests Document AI OCR.
```bash
# Windows
.venv\Scripts\python -m scripts.smoke_test ..\demo-data\sample_policy.pdf
# macOS / Linux
.venv/bin/python -m scripts.smoke_test ../demo-data/sample_policy.pdf
```
Expected result: `[PASS]` for Gemini, Embeddings, Firestore, Cloud Storage and Document AI OCR.

If a model name fails, change `GEMINI_MODEL` or `EMBEDDING_MODEL` in `backend/.env`.

### 6. Run the backend
```bash
# Windows
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
# macOS / Linux
.venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
Open http://localhost:8000/api/health. It should return `{"status":"ok"}`.

http://localhost:8000/api/diag calls every Google service once.

### 7. ADK test agent (optional)
Stop the backend first, because both use port 8000.
```bash
cd backend/agents
../.venv/bin/adk web --port 8000      # Windows: ..\.venv\Scripts\adk web --port 8000
```

---

## Phase 1 – UI/UX shell (demo data)

The frontend runs on **demo (mock) data**. It needs **no Google Cloud access and no backend**. A designer or frontend developer can start here.

### 1. Install the frontend packages
```bash
cd frontend
npm install
```
This takes about 3 minutes the first time. Warnings like `npm warn deprecated` or `install-scripts` are expected and harmless.

### 2. Check that it compiles
```bash
npx ng build --configuration development
```
Expected result: `Application bundle generation complete`, with no errors.

### 3. Start the app
```bash
npm start
```
Open **http://localhost:4200**. If that doesn't load, use **http://127.0.0.1:4200**. The page reloads automatically when you save a file.

**Cloud Shell instead:** run `bash scripts/dev-frontend.sh`, then click **Web Preview → Change port → 4200**.

### 4. Click through the demo story
| Page | What to check |
|---|---|
| `/` | The demo case banner shows ₹38,000 deducted, plus the 4 journey cards |
| `/ask` | Ask "Is my father's cataract surgery covered?". The agent steps appear one by one, then an answer card with page/clause chips |
| `/policy` | Limits, top 5 traps, waiting-period timeline |
| `/case` | Tick documents as collected; the progress bar updates |
| `/case/settlement` | ₹21,600 + ₹6,900 + ₹9,500 = ₹38,000, and the arithmetic check passes |
| `/case/letter` | Edit, copy, download or print the letter |
| `/upload` | Drop a PDF and watch the reading steps |

### 5. Where the demo data lives
- **Demo data:** `frontend/public/mocks/*.json`. Edit these files to change what the screens show.
- **Data formats (the API contract):** `frontend/src/app/models/models.ts`. The backend must return the same shapes.
- **Mock/real switch:** `USE_MOCKS` in `frontend/src/app/services/api.service.ts`. Keep it `true` until the backend provides the `/api/*` endpoints.

### 6. Run the frontend and backend together (optional)
Start the backend (Phase 0, step 6) on port 8000 and the frontend with `npm start`. Calls to `/api/*` are passed from port 4200 to port 8000 by `frontend/proxy.conf.json`.

`/status` then shows the backend and Google service checks.

---

## Troubleshooting
| Problem | Fix |
|---|---|
| `npx` / `node` not found right after installing | Close and reopen the terminal, or restart VS Code |
| gcloud fails with `CERTIFICATE_VERIFY_FAILED` | Your network inspects HTTPS traffic. Use Cloud Shell for gcloud and backend steps, or ask IT for the company root certificate |
| `python` opens the Microsoft Store (Windows) | Use `py -3.12` instead, or turn off the "App execution aliases" for Python in Windows Settings |
| PowerShell blocks scripts | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| Port 4200 or 8000 already in use | Stop the other terminal running it, or add `--port 4300` / `--port 8001` |
| `localhost:4200` doesn't open but the server is running | Use `http://127.0.0.1:4200` |
