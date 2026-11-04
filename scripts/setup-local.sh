#!/usr/bin/env bash
# One-time setup for running NorAI on your own PC with your own Gemini API key.
#
#   scripts/setup-local.sh          # then: scripts/start-dev.sh start
#
# It checks the prerequisites, creates venv/, installs the Python and frontend
# dependencies, writes .env in local mode (no login, no quotas, SQLite, every
# intake source including YouTube), and downloads the tutor's embedding model
# (~210 MB, once). Safe to re-run: an existing .env is never overwritten.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

say()  { printf '\n\033[1m%s\033[0m\n' "$*"; }
fail() { printf '\n\033[31mSetup stopped:\033[0m %s\n' "$*" >&2; exit 1; }

# ── Prerequisites ────────────────────────────────────────────────────────────
say "Checking prerequisites"
PY_BIN="${PYTHON:-python3}"
command -v "$PY_BIN" >/dev/null || fail "python3 not found. Install Python 3.12 or newer."
"$PY_BIN" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' \
  || fail "Python 3.12+ is required (found $("$PY_BIN" --version 2>&1)). Set PYTHON=/path/to/python3.12 to pick another."
command -v ffmpeg  >/dev/null || fail "ffmpeg not found. Install it (apt install ffmpeg / brew install ffmpeg)."
command -v ffprobe >/dev/null || fail "ffprobe not found (it ships with ffmpeg)."
command -v node    >/dev/null || fail "Node.js not found. Install Node 20.19+ (nvm recommended)."
NPM="$(command -v npm)" || fail "npm not found (it ships with Node.js)."
node -e 'const [a,b]=process.versions.node.split(".").map(Number); process.exit(a>20||(a===20&&b>=19)?0:1)' \
  || fail "Node 20.19+ is required (found $(node --version))."
echo "python $("$PY_BIN" --version 2>&1 | cut -d' ' -f2), node $(node --version), $(ffmpeg -version | head -1 | cut -d' ' -f1-3)"

# ── Python environment ───────────────────────────────────────────────────────
if [ ! -x venv/bin/python ]; then
  say "Creating venv/"
  "$PY_BIN" -m venv venv
fi
say "Installing Python dependencies"
venv/bin/python -m pip install --upgrade pip >/dev/null
venv/bin/python -m pip install -r requirements.txt

# ── Frontend ─────────────────────────────────────────────────────────────────
say "Installing frontend dependencies"
(cd frontend && "$NPM" ci)

# ── .env (local mode) ────────────────────────────────────────────────────────
if [ -f .env ]; then
  say ".env already exists, leaving it as is"
  grep -q '^NORAI_MODE=local' .env \
    || echo "Note: add NORAI_MODE=local to .env to skip login and quotas on this PC."
else
  say "Writing .env"
  echo "Get a free Gemini API key at https://aistudio.google.com/apikey"
  key="${GEMINI_API_KEY:-}"
  while [ -z "$key" ]; do
    read -r -s -p "Paste your Gemini API key (input hidden): " key; echo
  done
  umask 077
  cat > .env <<EOF
# NorAI local install (written by scripts/setup-local.sh). Never commit this file.
GEMINI_API_KEY=$key
# Single user on this PC: no login, no quotas, SQLite in outputs/, every intake
# source (YouTube included). Never use local mode on a public server.
NORAI_MODE=local
NORAI_ENV=development
EOF
  echo "Saved .env (readable only by you)."
fi

# ── Tutor embedding model (~210 MB, once) ────────────────────────────────────
say "Downloading the tutor's embedding model (skipped if already there)"
venv/bin/python -m tutor.local_embedding --download

say "Done. Start NorAI with:"
echo "  scripts/start-dev.sh start"
echo "then open http://localhost:5173 (stop it with: scripts/start-dev.sh stop)"
