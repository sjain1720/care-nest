#!/usr/bin/env bash
# Phase 0 connection test. Optional argument: a policy PDF to also test Document AI OCR.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PDF="${1:+$(realpath "$1")}"
cd "$ROOT/backend"
.venv/bin/python -m scripts.smoke_test ${PDF:+"$PDF"}
