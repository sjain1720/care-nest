#!/usr/bin/env bash
# Angular dev server on port 4200 (forwards /api to :8000). Open with Cloud Shell Web Preview > Change port > 4200.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/frontend"
# Web Preview reaches the server through a *.cloudshell.dev host, so the host check must be off.
npx ng serve --proxy-config proxy.conf.json --host 0.0.0.0 --port 4200 --disable-host-check
