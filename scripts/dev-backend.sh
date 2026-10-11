#!/usr/bin/env bash
# FastAPI with auto-reload on port 8000.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"
.venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
