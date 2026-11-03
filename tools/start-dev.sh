#!/usr/bin/env sh
# LumaCarve local-only development launcher for Linux.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON="$ROOT/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then
  echo "Missing shared .venv: run python3 tools/setup.py" >&2
  exit 1
fi
if [ ! -d "$ROOT/frontend/node_modules" ]; then
  echo "Missing Vue dependencies: cd frontend && npm install" >&2
  exit 1
fi
export LUMACARVE_DATA_DIR="$ROOT/LumaCarveData"
: "${LUMACARVE_INFERENCE_BACKEND:=disabled}"
export LUMACARVE_INFERENCE_BACKEND
"$PYTHON" -m uvicorn lumacarve_server.app:app --app-dir "$ROOT/backend" --host 127.0.0.1 --port 8000 &
API_PID=$!
cleanup() { kill "$API_PID" 2>/dev/null || true; wait "$API_PID" 2>/dev/null || true; }
trap cleanup EXIT INT TERM
cd "$ROOT/frontend"
npm run dev -- --host 127.0.0.1
