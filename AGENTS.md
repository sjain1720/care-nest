# Working in CareNest

CareNest is an Angular 19 + FastAPI hackathon monolith. Start with
`docs/REPO_MAP.md`, then read only the files for the requested feature.
`docs/DEVELOPMENT_QUEUE.md` records verified progress and ordered remaining work.
Historical planning documents describe proposals, not proof of implementation.

Use `python3 scripts/repo-map.py --query waiting` to locate symbols/routes;
add `--details` for imports and line numbers. No dependency installation needed.
Keep this map current when adding a route, service or workflow.

Contracts: update `backend/app/schemas.py` and
`frontend/src/app/models/models.ts` together. Mock JSON is in
`frontend/public/mocks`; mock results are not live-AI evidence.
Normal chat uses Python orchestration and Firestore retrieval; ADK is experimental.
Preserve page citations, unknowns, deterministic arithmetic and guest ownership.
Never infer pre-existing status from a diagnosis name alone or promise approval.

Run relevant tests first, then the backend suite:
`cd backend && .venv/bin/python -m unittest discover -s tests -t .`.
Frontend: `cd frontend && npm ci && NG_BUILD_MAX_WORKERS=2 npm run build`.
Use the bundled runtime if node/npm are absent. Do not run broad dependency
upgrades merely to clear an audit count. Deployment uses `scripts/deploy.sh`.

Keep environments, credentials, source policy PDFs, generated training data and
evaluation results ignored. Never print tokens or include them in URLs/logs.
Preserve untracked user documents. Report local vs deployed changes separately.
Do not claim tuning, retention, accuracy or isolation without verification.
