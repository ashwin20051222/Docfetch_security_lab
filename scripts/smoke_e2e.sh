#!/usr/bin/env bash
set -u
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API_DIR="$ROOT/apps/api"
WEB_DIR="$ROOT/apps/web"
API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-4173}"

cleanup() { pkill -f "uvicorn app.main:app" 2>/dev/null; pkill -f "vite preview" 2>/dev/null; }
trap cleanup EXIT

echo "== starting backend =="
rm -rf "$API_DIR/data"
mkdir -p "$API_DIR/data"
(
  cd "$API_DIR"
  DATABASE_URL="sqlite:///./data/docfetch.db" DATA_DIR="./data" \
    ./.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "$API_PORT" > /tmp/docfetch-api-e2e.log 2>&1
) &
API_PID=$!

echo "== starting web preview =="
(
  cd "$WEB_DIR"
  npm run preview -- --host 127.0.0.1 --port "$WEB_PORT" > /tmp/docfetch-web-e2e.log 2>&1
) &
WEB_PID=$!

# wait for API
for i in $(seq 1 20); do
  code=$(curl -s -m 2 -o /dev/null -w "%{http_code}" "http://127.0.0.1:$API_PORT/api/v1/health") || code="000"
  [ "$code" = "200" ] && break
  sleep 1
done
curl -s -m 3 "http://127.0.0.1:$API_PORT/api/v1/health" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"API health: status={d['status']} db={d['database']['status']}\")"

# wait for web
for i in $(seq 1 20); do
  code=$(curl -s -m 2 -o /dev/null -w "%{http_code}" "http://127.0.0.1:$WEB_PORT/") || code="000"
  [ "$code" = "200" ] && break
  sleep 1
done
echo "web root: $(curl -s -m 3 -o /dev/null -w '%{http_code}' http://127.0.0.1:$WEB_PORT/)"

echo "== proxied api through vite =="
curl -s -m 3 "http://127.0.0.1:$WEB_PORT/api/v1/health" -o /dev/null -w "proxied health: %{http_code}\n"

echo "== seeded targets =="
curl -s -m 3 "http://127.0.0.1:$API_PORT/api/v1/lab/targets" \
  | python3 -c "import sys,json; ts=json.load(sys.stdin); print('targets:', len(ts)); [print('  -', t['name'], t['base_url']) for t in ts]"

echo "== dashboard =="
curl -s -m 3 "http://127.0.0.1:$API_PORT/api/v1/dashboard/summary" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('dashboard:', {k: v for k, v in list(d.items())[:4]})"

echo "== favicon.yaml manifest ==="
curl -s -m 3 "http://127.0.0.1:$WEB_PORT/manifest.webmanifest" -o /dev/null -w "manifest: %{http_code}\n"

echo "OK"