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

# ffmpeg needed by yt-dlp download + audio extraction.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY . .
COPY --from=frontend /app/frontend/dist ./frontend/dist

ENV PYTHONUNBUFFERED=1
# SPA lives inside the image; keep it found regardless of CWD.
ENV NORAI_SPA_DIST=/app/frontend/dist
# Safe default: docs/redoc closed + CORS hardened unless overridden at runtime
# (Render staging can set NORAI_ENV=staging to keep /docs during QA).
ENV NORAI_ENV=production

EXPOSE 8000
# Bind to Render's injected PORT (default 10000) when set, else 8000 (local).
CMD python -m uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}
