#!/usr/bin/env bash
# ADK developer UI with the Phase 0 test agent on port 8000 (stop dev-backend first).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend/agents"
../.venv/bin/adk web --host 0.0.0.0 --port 8000
