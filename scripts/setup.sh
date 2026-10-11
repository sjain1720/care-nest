#!/usr/bin/env bash
# Cloud Shell setup: Python venv + backend packages, frontend packages, project config.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT="project-796a7c44-1092-4e43-ba6"

gcloud config set project "$PROJECT"

echo "==> Backend: virtual environment + packages"
cd "$ROOT/backend"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
[ -f .env ] || cp .env.example .env

echo "==> Frontend: npm packages"
cd "$ROOT/frontend"
npm install

echo
echo "Setup complete. Next: bash scripts/smoke-test.sh [path/to/policy.pdf]"
