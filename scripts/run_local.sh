#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export SEPARATION_BACKEND="${SEPARATION_BACKEND:-mock}"
export PYTHONPATH="$ROOT/backend"
export DB_URL="${DB_URL:-sqlite+aiosqlite:///$ROOT/data/secuencialive.db}"

echo "API en :8765 (SEPARATION_BACKEND=$SEPARATION_BACKEND)"
cd "$ROOT"
# shellcheck disable=SC1091
source backend/.venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8765
