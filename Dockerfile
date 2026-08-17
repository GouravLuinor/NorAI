# ── NorAI — single-container image (P5.4) ────────────────────────────────────
# Multi-stage: build the React SPA, then run FastAPI + serve frontend/dist.
# The backend serves the built SPA (see backend/main.py spa_middleware /
# spa_assets) so one container runs the whole product.

# ── Stage 1: frontend build ──────────────────────────────────────────────────
FROM node:22-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json frontend/.npmrc ./
RUN npm ci
COPY frontend/ ./

# VITE_* values are baked into the bundle at BUILD time. Render automatically
# passes service env vars to Docker as build args, so declaring these ARGs is
# all that's needed to inline real Supabase credentials. These are publishable
# (non-secret) values — never pass GEMINI_API_KEY / DATABASE_URL etc. here.
ARG VITE_SUPABASE_URL=""
ARG VITE_SUPABASE_ANON_KEY=""
ARG VITE_API_BASE_URL=""
ENV VITE_SUPABASE_URL="$VITE_SUPABASE_URL" \
    VITE_SUPABASE_ANON_KEY="$VITE_SUPABASE_ANON_KEY" \
    VITE_API_BASE_URL="$VITE_API_BASE_URL"
RUN npm run build

# ── Stage 2: python runtime ──────────────────────────────────────────────────
FROM python:3.12-slim
WORKDIR /app

# Runtime deps only (exact-pinned, P5.2); requirements-dev.txt stays out.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# ffmpeg needed by yt-dlp download + audio extraction; media-types provides /etc/mime.types.
# ca-certificates + curl: verify the POT provider download below.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg media-types ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

# ── PO-token provider (P8.x) ─────────────────────────────────────────────────
# bgutil-ytdlp-pot-provider-rs: a Rust single static binary (`bgutil-pot`) that
# generates proof-of-origin tokens, letting yt-dlp's `web` client pass YouTube's
# bot check from Render's datacenter IPs. The binary runs in HTTP server mode
# (port 4416) via scripts/entrypoint.sh; yt-dlp reaches it over the loopback
# NORAI_POT_SERVER_URL. The matching yt-dlp plugin zip is unzipped into the
# plugin dir so yt-dlp advertises `bgutil:http-...` as a PO Token Provider.
# Pinned release 1.2.2 (both artifacts match). If the download ever fails the
# build still succeeds with POT disabled — the fallback strategies remain.
ARG BGUTIL_POT_VERSION=v0.8.1
RUN set -eux; \
    curl -fsSL -o /usr/local/bin/bgutil-pot \
      "https://github.com/jim60105/bgutil-ytdlp-pot-provider-rs/releases/download/${BGUTIL_POT_VERSION}/bgutil-pot-linux-x86_64"; \
    chmod +x /usr/local/bin/bgutil-pot; \
    mkdir -p /root/.config/yt-dlp/plugins; \
    curl -fsSL -o /tmp/bgutil-ytdlp-pot-provider-rs.zip \
      "https://github.com/jim60105/bgutil-ytdlp-pot-provider-rs/releases/download/${BGUTIL_POT_VERSION}/bgutil-ytdlp-pot-provider-rs.zip" \
      && unzip -o /tmp/bgutil-ytdlp-pot-provider-rs.zip -d /root/.config/yt-dlp/plugins/bgutil-ytdlp-pot-provider \
      && rm -f /tmp/bgutil-ytdlp-pot-provider-rs.zip || \
    echo "WARN: POT provider download failed — continuing without it"

COPY . .
COPY --from=frontend /app/frontend/dist ./frontend/dist

ENV PYTHONUNBUFFERED=1
# SPA lives inside the image; keep it found regardless of CWD.
ENV NORAI_SPA_DIST=/app/frontend/dist
# Safe default: docs/redoc closed + CORS hardened unless overridden at runtime
# (Render staging can set NORAI_ENV=staging to keep /docs during QA).
ENV NORAI_ENV=production
# yt-dlp POT provider endpoint (loopback to the bgutil-pot server).
ENV NORAI_POT_SERVER_URL=http://127.0.0.1:4416

EXPOSE 8000
# Bind to Render's injected PORT (default 10000) when set, else 8000 (local).
# The entrypoint first spawns the bgutil POT server, then uvicorn.
CMD ["/app/scripts/entrypoint.sh"]
