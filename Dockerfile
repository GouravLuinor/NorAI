# ── NorAI — single-container image (P5.4) ────────────────────────────────────
# Multi-stage: build the React SPA, then run FastAPI + serve frontend/dist.
# The backend serves the built SPA (see backend/main.py spa_middleware /
# spa_assets) so one container runs the whole product.

# ── Stage 1: frontend build ──────────────────────────────────────────────────
FROM node:20-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json frontend/.npmrc ./
RUN npm ci
COPY frontend/ ./
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

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
