#!/usr/bin/env bash
# NorAI container entrypoint (P8.x): starts the bgutil POT server in the
# background (proof-of-origin token provider for YouTube downloads on datacenter
# IPs), then runs the FastAPI app. When the POT binary is absent (local dev /
# older image) the server is simply skipped and yt-dlp falls back to the
# non-POT strategies.
set -u

# bgutil-pot server mode (bgutil-ytdlp-pot-provider-rs). Config via
# NORAI_POT_SERVER_URL; env vars POT_SERVER_HOST / POT_SERVER_PORT also work.
if command -v bgutil-pot >/dev/null 2>&1; then
  echo "[entrypoint] starting bgutil POT server -> ${NORAI_POT_SERVER_URL:-http://127.0.0.1:4416}"
  bgutil-pot server --host 127.0.0.1 --port 4416 >/tmp/bgutil-pot.log 2>&1 &
  POT_PID=$!
  trap 'echo "[entrypoint] stopping bgutil POT server"; kill $POT_PID 2>/dev/null' EXIT INT TERM
else
  echo "[entrypoint] bgutil-pot not found; POT provider disabled (fallback strategies only)"
fi

echo "[entrypoint] starting uvicorn on :${PORT:-8000}"
exec python -m uvicorn backend.main:app --host 0.0.0.0 --port "${PORT:-8000}"