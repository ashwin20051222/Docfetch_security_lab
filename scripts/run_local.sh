#!/usr/bin/env bash
# run_local.sh — run ScribSave locally (API on :8000 + web app on :5173).
#
# Usage:
#   bash scripts/run_local.sh          # foreground, Ctrl+C to stop both
#   bash scripts/run_local.sh --bg     # start detached (pids in .run/)
#   bash scripts/run_local.sh --stop   # stop a detached instance
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_DIR="$ROOT/apps/api"
LOG_DIR="$ROOT/.run"
API_LOG="$LOG_DIR/api.log"
WEB_LOG="$LOG_DIR/web.log"
API_PID_FILE="$LOG_DIR/api.pid"
WEB_PID_FILE="$LOG_DIR/web.pid"

mkdir -p "$LOG_DIR"

set -a
# shellcheck disable=SC1091
[ -f "$ROOT/.env" ] && source "$ROOT/.env"
set +a

is_up() {
  local code
  code="$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 "http://127.0.0.1:$1/" 2>/dev/null || true)"
  [ -n "$code" ] && [ "$code" != "000" ]
}

stop_all() {
  for pid_file in "$API_PID_FILE" "$WEB_PID_FILE"; do
    if [ -f "$pid_file" ]; then
      kill "$(cat "$pid_file")" 2>/dev/null || true
      rm -f "$pid_file"
    fi
  done
  echo "[run-local] stopped."
}

if [ "${1:-}" = "--stop" ]; then
  stop_all
  exit 0
fi

ensure_deps() {
  if [ ! -x "$API_DIR/.venv/bin/python" ]; then
    echo "[run-local] creating Python venv …"
    python3 -m venv "$API_DIR/.venv"
    "$API_DIR/.venv/bin/pip" install --upgrade pip >/dev/null
  fi
  if ! "$API_DIR/.venv/bin/python" -c "import fastapi, playwright" >/dev/null 2>&1; then
    echo "[run-local] installing API requirements …"
    "$API_DIR/.venv/bin/pip" install -r "$API_DIR/requirements.txt"
  fi
  if [ ! -d "$ROOT/node_modules" ]; then
    echo "[run-local] npm install …"
    (cd "$ROOT" && npm install)
  fi
}

ensure_deps

if is_up 8000; then
  echo "[run-local] API already listening on :8000 (keeping it)"
else
  echo "[run-local] starting API on :8000 → $API_LOG"
  (cd "$API_DIR" && exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000) >"$API_LOG" 2>&1 &
  API_PID=$!
  echo "$API_PID" >"$API_PID_FILE"
fi

if is_up 5173; then
  echo "[run-local] web already listening on :5173 (keeping it)"
else
  echo "[run-local] starting web app on :5173 → $WEB_LOG"
  (cd "$ROOT/apps/web" && exec "$ROOT/node_modules/.bin/vite" --host 127.0.0.1) >"$WEB_LOG" 2>&1 &
  WEB_PID=$!
  echo "$WEB_PID" >"$WEB_PID_FILE"
fi

cleanup() {
  if [ -n "${FOREGROUND:-}" ]; then
    echo
    stop_all
  fi
}
trap cleanup EXIT INT TERM

echo "[run-local] waiting for services …"
for _ in $(seq 1 40); do
  is_up 8000 && is_up 5173 && break
  sleep 1
done

if is_up 8000 && is_up 5173; then
  echo
  echo "[run-local] ✓ ScribSave is running:"
  echo "      ──────────────────────────────────────────────"
  echo "      Web:   http://localhost:5173"
  echo "      API:   http://localhost:8000/api/v1/health"
  echo "      Logs:  $LOG_DIR/{api,web}.log"
  echo "      Stop:  bash scripts/run_local.sh --stop"
  echo "      ──────────────────────────────────────────────"
  if [ "${1:-}" = "--bg" ]; then
    echo "[run-local] background mode started." >&2
    exit 0
  fi
  FOREGROUND=1
  wait
else
  echo "[run-local] ERROR: services did not come up. Logs:"
  tail -n 15 "$API_LOG" 2>/dev/null || true
  tail -n 15 "$WEB_LOG" 2>/dev/null || true
  exit 1
fi