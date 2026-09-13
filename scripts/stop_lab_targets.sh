#!/usr/bin/env bash
# Stop the DocFetch Security Lab training targets.
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$(pwd)"

for pidfile in "$ROOT"/.run/lab-*.pid; do
  [[ -f "$pidfile" ]] || continue
  pid="$(cat "$pidfile")"
  name="$(basename "$pidfile" .pid)"
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null && echo "stopped: $name (pid $pid)"
  else
    echo "not running: $name"
  fi
  rm -f "$pidfile"
done