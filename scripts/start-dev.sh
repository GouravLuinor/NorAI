#!/usr/bin/env bash
# NorAI dev servers — one reliable bring-up for backend (8000) + frontend (5173).
#
# Why this exists (never reintroduce these traps — see AGENTS.md "Dev servers"):
#  - Helper scripts run from repo ROOT with `-m` so `import backend.*` resolves.
#  - Resolve `npm` from PATH (this machine uses nvm; /usr/bin/npm does not exist).
#  - Health-check by HTTP PROBE (curl /docs), never by reading the log file —
#    a healthy uvicorn at --log-level warning prints nothing (0-byte log).
#  - Idempotent: if a port is already serving, DO NOT relaunch (a second bind
#    attempt on an occupied port spins at ~120% CPU in a bind-retry loop).
#
# Usage:
#   scripts/start-dev.sh start     # start backend + frontend (daemonized)
#   scripts/start-dev.sh stop      # stop both
#   scripts/start-dev.sh status    # probe both ports
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/venv/bin/python"
LGDIR="$ROOT/.tmp/dev"
mkdir -p "$LGDIR"

BE_TAG="uvicorn backend.main:app"
FE_TAG="node $ROOT/frontend/node_modules/.bin/vite"
BE_URL="http://127.0.0.1:8000/docs"
FE_URL="http://127.0.0.1:5173"

probe() { curl -s -o /dev/null --max-time 2 "$1" 2>/dev/null && return 0 || return 1; }

start_backend() {
  if probe "$BE_URL"; then echo "backend: already up (port 8000)"; return 0; fi
  echo "backend: launching uvicorn daemon (repo root, -m) ..."
  # --log-level info so the log proves startup; probe is the source of truth.
  setsid "$PY" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 \
    --log-level info < /dev/null >> "$LGDIR/backend.log" 2>&1 &
  for i in $(seq 1 30); do probe "$BE_URL" && { echo "backend: UP (/docs 200)"; return 0; }; sleep 1; done
  echo "backend: FAILED to reach $BE_URL — see $LGDIR/backend.log" >&2; return 1
}

start_frontend() {
  if probe "$FE_URL"; then echo "frontend: already up (port 5173)"; return 0; fi
  local npm
  npm="$(command -v npm)" || { echo "frontend: npm not found on PATH" >&2; return 1; }
  echo "frontend: launching vite daemon ..."
  ( cd "$ROOT/frontend" && setsid "$npm" run dev < /dev/null >> "$LGDIR/frontend.log" 2>&1 & )
  for i in $(seq 1 30); do probe "$FE_URL" && { echo "frontend: UP"; return 0; }; sleep 1; done
  echo "frontend: FAILED to reach $FE_URL — see $LGDIR/frontend.log" >&2; return 1
}

cmd="${1:-start}"
case "$cmd" in
  start) start_backend && start_frontend ;;
  stop)
    pkill -f "$BE_TAG" 2>/dev/null && echo "backend: stopped" || echo "backend: not running"
    pkill -f "$FE_TAG" 2>/dev/null && echo "frontend: stopped" || echo "frontend: not running"
    ;;
  restart)
    pkill -f "$BE_TAG" 2>/dev/null && echo "backend: stopped" || echo "backend: not running"
    pkill -f "$FE_TAG" 2>/dev/null && echo "frontend: stopped" || echo "frontend: not running"
    sleep 1
    start_backend && start_frontend
    ;;
  status)
    probe "$BE_URL" && echo "backend:  UP  ($BE_URL)" || echo "backend: DOWN"
    probe "$FE_URL" && echo "frontend: UP  ($FE_URL)" || echo "frontend: DOWN"
    ;;
  *) echo "usage: $0 {start|stop|restart|status}"; exit 1 ;;
esac