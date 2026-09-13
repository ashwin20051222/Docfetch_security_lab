#!/usr/bin/env bash
# DocFetch Security Lab — fullstack integration test.
#
# Verifies the real API, the lab target servers, and the web frontend as a
# running system: registration, the lab engine producing real findings, report
# export, and the bundled frontend. Requires a working Python venv plus npm
# deps (see README "Development").
set -eu

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
API_PID=""
WEB_PID=""
TARGET_PIDS=""
# The built frontend bakes VITE_API_BASE_URL at build time (default :8000),
# so the API must listen there. Fail loudly if something else owns the port.
API_PORT="8000"
WEB_PORT="4137"
CONFIG_DIR="$ROOT/apps/api"
VENV="$CONFIG_DIR/.venv"

trap cleanup EXIT

cleanup() {
  [ -n "$TARGET_PIDS" ] && kill $TARGET_PIDS 2>/dev/null || true
  [ -n "$WEB_PID" ] && kill "$WEB_PID" 2>/dev/null || true
  [ -n "$API_PID" ] && kill "$API_PID" 2>/dev/null || true
}

step() { printf '\n== %s ==\n' "$*"; }
fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
wait_for() {
  local url="$1" what="$2" i code
  for i in $(seq 1 30); do
    code=$(curl -s -m 2 -o /dev/null -w '%{http_code}' "$url" || true)
    [ "$code" = "200" ] && return 0
    sleep 1
  done
  fail "$what did not come up (last status $code)"
}

cd "$ROOT"

if curl -s -m 1 http://127.0.0.1:$API_PORT/api/v1/health -o /dev/null 2>/dev/null; then
  fail "port $API_PORT is already serving an API — stop it first (npm run lab:down, or kill uvicorn)."
fi

rm -rf "$CONFIG_DIR/integration-data"

step "starting lab targets"
bash scripts/run_lab_targets.sh
sleep 2
TARGET_PIDS=$(pgrep -f 'lab-target.*server.py' | tr '\n' ' ' || true)

step "starting backend on :$API_PORT with isolated data dir"
mkdir -p "$CONFIG_DIR/integration-data"
PY_BIN="$VENV/bin/uvicorn"
if [ ! -x "$PY_BIN" ]; then
  PY_BIN="$(command -v uvicorn || echo python3 -m uvicorn)"
fi
(
  cd "$CONFIG_DIR"
  DATABASE_URL="sqlite:///./integration-data/test.db" DATA_DIR="./integration-data" \
    "$PY_BIN" app.main:app --host 127.0.0.1 --port "$API_PORT" \
    > /tmp/docfetch-int-api.log 2>&1
) &
API_PID=$!
wait_for "http://127.0.0.1:$API_PORT/api/v1/health" "backend"

step "starting bundled web app on :$WEB_PORT"
if [ ! -f "$ROOT/apps/web/dist/index.html" ]; then
  npm run build --workspace apps/web
fi
(
  cd "$ROOT/apps/web"
  npm run preview -- --host 127.0.0.1 --port "$WEB_PORT" > /tmp/docfetch-int-web.log 2>&1
) &
WEB_PID=$!
wait_for "http://127.0.0.1:$WEB_PORT/" "frontend"

step "confirming seeded targets exist"
curl -s "http://127.0.0.1:$API_PORT/api/v1/lab/targets" \
  | python3 -c "import sys,json; ts=json.load(sys.stdin); assert len(ts)>=3, 'expected >=3 targets'; print(f'{len(ts)} targets OK')"

step "registering a live weak target and running the lab engine"
WEAK_NAME="Int: Weak Client Paywall $(date +%s)"
WEAK_ID=$(curl -s -X POST "http://127.0.0.1:$API_PORT/api/v1/lab/targets" \
  -H 'Content-Type: application/json' \
  -d "{\"name\":\"$WEAK_NAME\",\"base_url\":\"http://127.0.0.1:9102\",\"environment_type\":\"local\",\"auth_status\":\"none\",\"allowed_test_profiles\":[\"client-side-access-control\"]}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
curl -s -X POST "http://127.0.0.1:$API_PORT/api/v1/lab/tests" \
  -H 'Content-Type: application/json' \
  -d "{\"target_id\":\"$WEAK_ID\",\"profile\":\"client-side-access-control\"}" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('status') in ('passed','failed'), d; print('lab engine ran:', d.get('status'), '-', d.get('title'))"

step "verifying the finding was recorded"
curl -s "http://127.0.0.1:$API_PORT/api/v1/lab/findings" \
  | python3 -c "import sys,json; fs=json.load(sys.stdin); assert any(f['severity']=='high' and f['status']=='open' for f in fs), 'expected a HIGH open finding'; print(f'{len(fs)} finding(s) recorded, one HIGH/open confirmed')"

step "exporting a report"
REPORT_ID=$(curl -s -X POST "http://127.0.0.1:$API_PORT/api/v1/lab/reports" \
  -H 'Content-Type: application/json' \
  -d "{\"target_id\":\"$WEAK_ID\",\"formats\":[\"json\"]}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
curl -s -o /dev/null -w "report download HTTP %{http_code}\n" "http://127.0.0.1:$API_PORT/api/v1/lab/reports/$REPORT_ID/download"

step "frontend bundle references the live API"
curl -s "http://127.0.0.1:$WEB_PORT/" | grep -qi "docfetch" \
  && echo "frontend serves DocFetch" \
  || fail "frontend index.html did not mention DocFetch"

step "cleanup"
curl -s -X DELETE "http://127.0.0.1:$API_PORT/api/v1/lab/targets/$WEAK_ID" -o /dev/null || true
sleep 1
rm -rf "$CONFIG_DIR/integration-data"

echo
echo "INTEGRATION PASS"