#!/usr/bin/env bash
# Launch the three DocFetch Security Lab training targets.
# Each is a zero-dependency stdlib Python server, bound to 127.0.0.1 only.
# Stop them with scripts/stop_lab_targets.sh
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$(pwd)"
LAB="$ROOT/lab-target"
mkdir -p "$ROOT/.run"

for entry in secure-paywall:9101 weak-client-paywall:9102 weak-direct-file:9103; do
  name="${entry%%:*}"
  port="${entry##*:}"
  pidfile="$ROOT/.run/lab-$name.pid"
  if [[ -f "$pidfile" ]] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
    echo "already running: $name (pid $(cat "$pidfile"))"
    continue
  fi
  ( cd "$LAB/$name" && PORT="$port" nohup python3 server.py >"$ROOT/.run/lab-$name.log" 2>&1 &
    echo $! > "$pidfile"
  )
  echo "started: $name on $port (pid $(cat "$pidfile"))"
done

sleep 1
for port in 9101 9102 9103; do
  code="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$port/health" || true)"
  echo "health $port -> $code"
done