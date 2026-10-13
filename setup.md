# CareNest – Local Setup Guide

How a new team member sets up CareNest on their own computer.
This file is updated after every phase. Each phase section lists only what that phase **adds**, so follow the sections in order.

| Phase | What you can run locally after it |
|---|---|
| Phase 0 – Foundation | Backend (FastAPI) talking to Google Cloud, plus the connection test |
| Phase 1 – UI/UX shell | The full web app on demo data (no Google Cloud needed) |
| Phase 2 – Policy understanding | Upload a real policy PDF, get extracted facts and cited answers (needs Google Cloud). Unit tests run without it |
| Phase 3 – Bill and settlement analyser | Upload a bill and a settlement letter: missing pages, arithmetic, room-rent cut, non-payables, estimate, every deduction explained (needs Google Cloud). Unit tests run without it |
| Phase 4 – Claim Copilot, letters, ADK agents | Ask anything about the policy, bill, settlement or documents; 4 kinds of letters; saved checklist; query helper; ADK agent team in `adk web` (needs Google Cloud). Unit tests run without it |

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
npx ng build --configuration development   # quick check
npx ng build                               # production build, the same one Cloud Run uses
```
Expected result: `Application bundle generation complete`, with no errors.

The production build is set to not download Google Fonts (`"fonts": false` in `angular.json`), so it also works behind company networks that inspect HTTPS traffic.

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
| `/policy` | Click a "Page 7 · Clause 3.2" chip: the PDF opens at that page. Try the room simulator: a ₹7,500 room gives ₹21,600 extra |
| `/case/query` | Click "Explain this query": steps appear, then 3 documents and a draft reply |
| `/ask` | Ask "Is my father's cataract surgery covered?". The agent steps appear one by one, then an answer card with page/clause chips |
| `/case` | Tick documents as collected; the progress bar updates |
| `/case/settlement` | ₹21,600 + ₹6,900 + ₹9,500 = ₹38,000, and the arithmetic check passes |
| `/case/letter` | Edit, copy, download or print the letter |
| `/upload` | Drop a PDF and watch the reading steps |

### 5. Where the demo data lives
- **Demo data:** `frontend/public/mocks/*.json`. Edit these files to change what the screens show.
- **Demo PDFs:** `frontend/public/demo/*.pdf`, opened by the citation chips. To regenerate them after editing `demo-data/make_demo_pdfs.py`:
  ```bash
  python demo-data/make_demo_pdfs.py        # Windows: py -3.12 demo-data\make_demo_pdfs.py
  ```
  This writes the same PDFs to `demo-data/` (used by the connection test and the bucket upload) and to `frontend/public/demo/`.
- **Data formats (the API contract):** `frontend/src/app/models/models.ts`. The backend must return the same shapes.
- **Mock/real switch:** `USE_MOCKS` in `frontend/src/app/services/api.service.ts`. Keep it `true` until the backend provides the `/api/*` endpoints.

### 6. Run the frontend and backend together (optional)
Start the backend (Phase 0, step 6) on port 8000 and the frontend with `npm start`. Calls to `/api/*` are passed from port 4200 to port 8000 by `frontend/proxy.conf.json`.

`/status` then shows the backend and Google service checks.

---

## Phase 2 – Policy understanding

No new tools or packages. `backend/requirements.txt` is unchanged.

### 1. Unit tests (no Google Cloud, no packages needed)
These test clause splitting, quote checking and waiting-period dates on the demo policy:
```bash
cd backend
python -m unittest discover -s tests -t .      # Windows: py -3.12 -m unittest discover -s tests -t .
```
Expected result: `Ran 23 tests ... OK`.

### 2. Run the real pipeline (needs Phase 0: sign-in, `.env`, packages)
In terminal 1, start the backend (Phase 0, step 6). In terminal 2, from the repo root:
```bash
# Upload the demo policy (OCR + clauses + facts; about 30-60 seconds the first time)
curl -F "file=@demo-data/sample_policy.pdf" http://localhost:8000/api/documents

# Extracted facts
curl -s http://localhost:8000/api/policy | python -m json.tool

# A cited answer
curl -s -X POST http://localhost:8000/api/copilot/ask -H "Content-Type: application/json" \
  -d '{"question": "Is my father'"'"'s cataract surgery covered?"}' | python -m json.tool

# All 12 test questions with accuracy scores
python eval/run_policy_eval.py http://localhost:8000
```
Uploading the same PDF again finishes instantly, because the earlier result is reused.

**Add schedule details.** Most policy PDFs are *wordings* without your personal schedule, so the start date, sum insured, members and room limit may be missing. Add them on `/policy` → **Add or correct**, or with:
```bash
curl -s -X PUT http://localhost:8000/api/policy/details -H "Content-Type: application/json" \
  -d '{"startDate": "2024-03-12", "sumInsured": 500000, "roomRentPerDay": 5000}'
```
The waiting-period dates are then recomputed.

**Check many policies at once** (public policy wordings only, never bills):
```bash
python eval/run_dataset_check.py http://localhost:8000 "path/to/policies/test data"
```

### 3. Use live data in the web app
1. Start the frontend (`npm start`) with the backend running.
2. Open `/status`. Under **Live or demo data**, tick **My policy**, **Ask** and **Upload documents**, then click **Save and reload**.
3. On `/upload`, drop `demo-data/sample_policy.pdf`.
4. On `/policy`, you'll see the real extracted facts. Citation chips open the uploaded PDF at the right page.
5. On `/ask`, answers come from the backend.

The case, bill, settlement, letter and query pages stay on demo data until later phases. Untick everything to go back to full demo mode.

### 4. ADK Policy Specialist (optional)
```bash
bash scripts/adk-web.sh        # or: cd backend/agents && ../.venv/bin/adk web --port 8000
```
Pick **policy_agent** in the ADK page and ask "Is cataract covered?". It calls `search_policy` and `waiting_period_status`.

---

## Phase 3 – Bill and settlement analyser

No new tools or packages.

### 1. Unit tests (no Google Cloud needed)
```bash
cd backend
python -m unittest discover -s tests -t .      # Windows: py -3.12 -m unittest discover -s tests -t .
```
Expected: `Ran 44 tests ... OK`. These cover the room-rent maths on the demo bill (₹21,600), missing "Page X of N" pages, arithmetic errors, the non-payable list, settlement reconciliation, the checklist, and masking of phone numbers, emails and ID numbers.

### 2. Try it with the demo documents (needs the Phase 2 setup)
With the backend running, and after uploading the demo policy and adding a room limit of 5000:
```bash
curl -s -F "file=@demo-data/hospital_bill.pdf" -F "docType=Hospital bill" http://localhost:8000/api/documents
curl -s -F "file=@demo-data/settlement_letter.pdf" -F "docType=Settlement letter" http://localhost:8000/api/documents
curl -s http://localhost:8000/api/case/settlement | python -m json.tool
```
In the web app:
1. On `/status`, tick **My case**, **Hospital bill check** and **Settlement breakdown**.
2. On `/upload`, pick the type (or **Detect automatically**) and drop the PDFs.
3. Open `/case/bill` and `/case/settlement`.

### 3. Real bills
The dataset's medical bills contain **real patient details**. Use them only in your own private project, never in the public demo or the repo. `eval/run_bill_check.py` runs them in bulk and prints no names. See `googleCloudStepsForThisPhase.md` step 3.3.

---

## Phase 4 – Claim Copilot, letters and ADK agents

No new tools or packages.

### 1. Unit tests (no Google Cloud needed)
```bash
cd backend
python -m unittest discover -s tests -t .      # Windows: py -3.12 -m unittest discover -s tests -t .
```
Expected: `Ran 54 tests ... OK`. The new tests cover keyword routing, case facts with sources, all 4 letter types, the check for invented amounts, saved checklist ticks, and the "Claim rejected" stage.

### 2. Try it (needs the Phase 2 and 3 setup)
- **Ask:** with **Ask** live on `/status`, ask about the bill ("How much will I pay?"), the settlement ("Why was money deducted?") or documents. The first progress step shows which specialist answered.
- **Letters:** with **Letter to insurer** live, choose a letter type on `/case/letter`. Drafts come from the backend with checked amounts and a list of documents to attach.
- **Checklist:** with **My case** live, ticks on `/case` are saved.
- **Query helper:** with **Insurer query helper** live, `/case/query` uses your real policy.

### 3. ADK agent team
```bash
bash scripts/adk-web.sh      # pick "claim_copilot" (or the single "policy_agent")
```
The agents live in `backend/app/adk_copilot.py`, and their tools in `backend/app/agent_tools.py`.

---

## Phase 5 – Integration and visual polish

No new tools or packages.

### 1. Checks (no Google Cloud needed)
```bash
cd backend
python -m unittest discover -s tests -t .      # Windows: py -3.12 -m unittest discover -s tests -t .
cd ../frontend && npx ng build
```
Expected: `Ran 57 tests ... OK` (on a laptop without the backend packages: `OK (skipped=2)`) and "Application bundle generation complete".

### 2. What's new in the app
- **Header button:** "Demo case" or "Your documents" ("Demo (partly live)" if only some features are live on `/status`). Clicking it switches every feature and reloads the page.
- **Ask:** in live mode, the progress steps appear one by one as the backend works.
- **Home:** in live mode with no documents, **Load the demo case with real AI** runs the demo PDFs through the real pipeline (takes 1–2 minutes the first time) and then opens the settlement breakdown.
- **Settlement breakdown:** waterfall chart; click a column to open that deduction.
- **Errors:** a short message at the bottom of the screen if the server can't be reached.

The demo loader finds the PDFs in `backend/static/demo` (inside the container) or in `demo-data/`. If they are missing, run `python demo-data/make_demo_pdfs.py`.

---

## UI refresh, part 1 – dashboard, search and floating assistant

No new tools or packages (Material autocomplete is part of `@angular/material`, which is already installed).

```bash
cd frontend && npx ng build      # or: npm start, then open http://127.0.0.1:4200
```
What to try:
- **Dashboard (`/`):** each tile and "Needs your attention" row opens the exact section.
- **Search:** click the search bar (or press `/`). Try "room", "cataract", "9500" or "missing". Enter opens the top result; "Ask: …" sends the text to the assistant.
- **Assistant:** the button at the bottom right opens a chat on any page. Its suggestions change with the page. "Open in full page" continues the same chat on `/ask`.
- **Reduced motion:** turn on "Show animations" = off (Windows) or "Reduce motion" (Mac/phone) to check that the app stays still.

### Dark mode (part 2)
The app opens in **dark mode**. The sun/moon button in the header switches to light (and back). The choice is remembered in the browser (`localStorage` key `carenest.theme`); to reset it, run `localStorage.removeItem('carenest.theme')` in the browser console.

### Chat bar, plain language and next steps (part 3)
No new packages. After `npm start`:
- The glowing **Ask anything** bar is at the bottom of every page. Type a question and press Enter, or type a word like "room" and pick a place from the suggestions.
- Each page starts with **What to do now** steps.
- Backend: the shared writing rules are in `backend/app/services/plain_language.py`. Change them there and every Gemini answer follows.

### Part 4 – settings, Hindi, More tab
No new packages (the menu and tooltip are part of `@angular/material`).
- **Settings:** the **Aa** button in the header (on phones: **More** tab → Settings) switches **English / हिन्दी** and the **text size** (A− / A+). Both are saved in the browser (`carenest.lang`, `carenest.textSize`).
- **Hindi answers** need live mode (the backend writes them). In demo mode the answers stay in English, with a note.
- **Welcome card:** shown once on the dashboard. To see it again: `localStorage.removeItem('carenest.onboarded')`.
- Unit tests: `Ran 60 tests ... OK` (on the laptop: `OK (skipped=2)`).

### Part 5 – claim diary and the insurer's reply
No new packages.
- New page **The insurer replied** (`/case/reply`, in the claim menu and the phone's More sheet).
- To try the full flow in demo mode:
  1. Open **Write to the insurer**, then tap **I've sent it**.
  2. Open **The insurer replied** and tap **Read their reply** (a sample reply is filled in).
  3. Tap **I'm happy – close my claim**.
- Demo mode keeps the diary, checklist ticks and letter edits in this browser. Keys: `carenest.timeline`, `carenest.checklist`, `carenest.letter.<kind>`.
- To start the demo again:
  `['carenest.timeline','carenest.checklist'].forEach(k => localStorage.removeItem(k))`
- Unit tests: `Ran 71 tests ... OK` (on the laptop: `OK (skipped=2)`).

### Part 32 – guest sessions, coverage estimate, delete my data
No new packages.
- **Each visitor gets a private guest session.** The backend sets an HttpOnly cookie `cn_session` on the first `/api` call. That visitor's claim, uploaded claim files, active policy and typed-in policy details are kept under it, so two people using the app never see each other's data. The data is deleted after 7 days without use.
- Testing the backend with `curl`: keep the cookie between calls, otherwise every call starts a new, empty session:
  ```bash
  curl -s -c jar.txt -b jar.txt -F "file=@demo-data/sample_policy.pdf" http://localhost:8000/api/documents
  curl -s -c jar.txt -b jar.txt http://localhost:8000/api/policy | head -c 300
  curl -s -c jar.txt -b jar.txt -X DELETE http://localhost:8000/api/session -o /dev/null -w "%{http_code}\n"   # 204 = your data is deleted
  ```
- `eval/run_policy_eval.py` now uploads the demo policy and its schedule details itself, in its own session. You no longer need to upload it first. `eval/run_bill_check.py` and `eval/run_dataset_check.py` keep one session for all their calls.
- In the web app: footer › Privacy › **Delete my data** clears your session on the server (live mode) and the demo notes kept in this browser. *(Button removed in part 44; `DELETE /api/session` still works.)*
- The dashboard and **My policy** show **Estimated coverage remaining** (sum insured minus what the insurer paid on the claims recorded here), with the assumptions listed. Demo: ₹5,00,000 − ₹2,08,000 = ₹2,92,000 (58% left).
- Light mode is the default. Theme choices made before this are reset once (key `carenest.theme.v2`).
- Unit tests: `Ran 80 tests ... OK` (on the laptop: `OK (skipped=2)`).

### Part 33 – list of claims, past claims, coverage across the policy year
No new packages.
- **My claim › Your claims** lists every claim on the policy: the one open on the page first, then earlier ones, newest first. Each line shows the date, hospital, amount paid and amount claimed, and a status: waiting for a decision, paid in full, paid with cuts, or refused.
- **Start a new claim** (live mode) keeps the current claim, with its files, in the list and opens an empty one. **Open** brings an earlier claim back, and the current one goes into the list. Letter drafts are cleared when you switch, because they belong to one claim.
- **Add a past claim** records a claim made before CareNest, typed in from the insurer's payment letter. Only the discharge date and the amount paid are required; enter 0 if the claim was refused. Earlier claims can be deleted, never the open one.
- **Estimated coverage remaining** now subtracts every claim paid in the **current policy year**, worked out from the policy start date. Claims from earlier years and claims not yet decided are not counted. Demo: ₹5,00,000 − ₹2,08,000 − ₹42,000 (dengue, June 2026) = **₹2,50,000 (50% left)**. The cataract claim from November 2025 falls in the previous policy year.
- Demo mode: the list comes from `public/mocks/claims.json`. Added and deleted past claims are kept in this browser (key `carenest.claims`). To reset: `localStorage.removeItem('carenest.claims')`.
- Backend (keep the cookie between calls):
  ```bash
  J="-c jar.txt -b jar.txt"
  curl -s $J http://localhost:8000/api/claims
  curl -s $J -H "Content-Type: application/json" -d '{"date":"2026-06-05","approvedAmount":42000,"claimedAmount":46500,"title":"Dengue fever"}' http://localhost:8000/api/claims/past
  curl -s $J -X POST http://localhost:8000/api/claims/new           # current claim moves into the list
  curl -s $J -X POST http://localhost:8000/api/claims/<id>/open     # bring an earlier CareNest claim back
  curl -s $J -X DELETE http://localhost:8000/api/claims/<id>
  ```
- Unit tests: `Ran 88 tests ... OK` (on the laptop: `OK (skipped=2)`).

### Part 34 – Start a new claim on the dashboard and at the top of My claim
No new packages, no backend change.
- **Dashboard:** a **Your claims** card above the coverage estimate. It shows the open claim and how many earlier claims there are, with **Start a new claim** and **All your claims**. When the open claim is still empty, it shows **Add the bill** instead.
- **My claim:** **Start a new claim** and **All your claims** buttons next to the page title.
- **Demo mode now supports it:**
  - **Start a new claim** puts the sample claim aside, with its diary and ticks, and opens an empty claim. The empty claim has no bill and no insurer's letter, and the next step is "Start with the hospital bill".
  - **Open** on the sample claim in the list brings it back.
  - A new demo claim stays empty, because demo uploads aren't saved.
  - Reset: `['carenest.claims','carenest.timeline','carenest.checklist'].forEach(k => localStorage.removeItem(k))`

### Part 43 – general questions, bill photos, checking the bill reading
No new packages.
- **General questions without a policy:** "What is a waiting period?" now gets a plain general answer, labelled **General information – not from your policy**, with **Check this in your own policy** and **Try the demo case**. Questions about *your* cover ("Does my policy cover…", "Can I claim…") still need your policy: CareNest asks for it and offers the demo instead of guessing. The router decides general vs your own; if Gemini is down, simple keywords decide ("my", "am I", "can I", …).
- **Bill photos:** bills and insurer letters can be uploaded as JPG, PNG or WebP photos (phones show a **Take a photo** button). Policies stay PDF-only. For a bill with several pages, upload one PDF with every page.
- **Check what we read:** after a bill is read, the bill page asks you to compare the details with the paper bill. **Yes, these are right**, or **Correct something** to change the hospital, dates, patient, total or any charge (add or remove lines). In live mode every check runs again on your values (no AI); letters warn until the bill has been checked. In demo mode the corrections are kept in this browser (key `carenest.billReview`).
- Backend test (keep the cookie): `curl -s -c j.txt -b j.txt -F "file=@bill.jpg" -F "docType=Hospital bill" http://localhost:8000/api/documents`, then `PUT /api/case/bill` (see `googleCloudStepsForThisPhase.md`, part 43).
- Unit tests: `Ran 97 tests ... OK` (on the laptop: `OK (skipped=2)`).

### Deploy the prototype on Netlify or Vercel (static, demo mode)
No new packages. The frontend runs fully on demo data (`public/mocks`, `public/demo`), so it works as a static site with no backend.

**Build** (in `frontend/`):
```powershell
npx ng build --configuration production
```
The output is `frontend/dist/frontend/browser/` (index.html, JS, CSS, `mocks/`, `demo/` and `_redirects`). The folder is git-ignored.

**Netlify:**
- **Drag and drop:** open app.netlify.com › Add new site › Deploy manually, then drop the `frontend/dist/frontend/browser` folder (or a zip of its contents).
- **From the repository:** base directory `frontend`. `frontend/netlify.toml` sets the build command (`npm run build`), the publish folder (`dist/frontend/browser`) and Node 20.
- `_redirects` sends every page route (e.g. `/case/settlement`) to the app, so refreshing any page works.

**Vercel:** import the repository, set the root directory to `frontend`, and leave the framework preset as Other. `frontend/vercel.json` sets the build command, the output folder and the page-route rewrite. With the CLI: `cd frontend; npx vercel --prod`. (This uses npx, so nothing is installed globally.)

**Live mode (optional):** the static site has no `/api`. To use the Cloud Run backend, proxy `/api` to it, so the guest-session cookie stays on the same site:
- Netlify: in `public/_redirects`, remove the `#` from the `/api/*` line, put your Cloud Run URL, and rebuild. Keep it above the `/*` line.
- Vercel: in `vercel.json`, add `{ "source": "/api/(.*)", "destination": "https://YOUR-CLOUD-RUN-URL/api/$1" }` as the first rewrite.

Then tick the features on `/status`. Without the proxy, `/status` shows "Backend: unreachable", and the demo still works everywhere.

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
