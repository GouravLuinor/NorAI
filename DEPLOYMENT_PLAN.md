# NorAI — End-to-End Production Deployment & Infrastructure Guide

This document provides a comprehensive, project-specific, and practical deployment strategy for taking **NorAI** from local development (`localhost`) to a public, production-ready SaaS on the web.

---

## Executive Summary & Recommended Stack (MVP Launch)

For the initial stage (**4–5 demo users/testers**, negligible background traffic, budget optimization), the recommended architecture minimizes operational complexity while maintaining 100% feature fidelity (including `faster-whisper` CPU transcription and `ffmpeg` video processing).

```
                      +------------------------------------------+
                      |         Cloudflare (DNS & SSL)           |
                      |          app.norai.ai / API              |
                      +--------------------+---------------------+
                                           |
                   +-----------------------+-----------------------+
                   |                                               |
                   v                                               v
     +---------------------------+                   +---------------------------+
     |     Vercel / CF Pages     |                   |  Railway / Render / VPS   |
     |   React 19 Vite SPA App   |                   |  FastAPI + Docker Backend |
     |  (Static Hosting & CDN)   |                   |   (Whisper, FFmpeg, RAG)  |
     +-------------+-------------+                   +-------------+-------------+
                   |                                               |
                   | (Client Auth)                                 | (SQLAlchemy / asyncpg)
                   v                                               v
     +---------------------------+                   +---------------------------+
     |       Supabase Auth       |                   |  Supabase Postgres DB     |
     |  (JWKS, JWT verification) |                   | (Lectures, Users, Quotas) |
     +---------------------------+                   +---------------------------+
                                                                   |
                                                                   | (Local Persistent Vol
                                                                   |  or S3 / R2 Bucket)
                                                                   v
                                                     +---------------------------+
                                                     |    Artifacts / ChromaDB   |
                                                     |     /outputs/<lecture_id> |
                                                     +---------------------------+
```

### Initial Monthly Bill Summary (0–10 Demo Users)

| Service | Provider & Plan | Est. Monthly Cost | Notes |
| :--- | :--- | :--- | :--- |
| **Domain** | Namecheap / Porkbun (`norai.app` or `.ai`) | **$1.00 – $2.50** | ~$12–$30/yr domain registration |
| **DNS & CDN** | Cloudflare Free Tier | **$0.00** | Free SSL, DDoS protection, Caching |
| **Frontend** | Vercel Free / Cloudflare Pages | **$0.00** | Generous free static hosting |
| **Backend & Pipeline**| Railway Starter ($5) / Hetzner Cloud CX22 ($4.50) / Render Standard ($7) | **$4.50 – $7.00** | 2-4 GB RAM required for local Whisper/FFmpeg |
| **Database & Auth** | Supabase Free Tier | **$0.00** | 500 MB Postgres, Auth, JWKS, Daily backups |
| **AI LLM & Vision** | Google Gemini API (`gemini-3.1-flash-lite`) | **$0.50 – $2.00** | Pay-per-token ($0.25/1M in, $1.50/1M out) |
| **Object Storage** | Cloudflare R2 / Local Disk Volume | **$0.00** | 10 GB free on Cloudflare R2 or included VPS disk |
| **Monitoring** | GlitchTip Free / Better Stack / Sentry Free | **$0.00** | Error tracking & uptime pinging |
| **TOTAL INITIAL COST** | | **~$6.00 – $10.00 / month** | |

> **Note on compute**: the MVP is deployed to an **already-owned Hostinger KVM 1 VPS** (1 vCPU / 4 GB / 50 GB), so the backend-compute line item is effectively **$0 additional**. Marginal monthly cost = Supabase Free ($0) + Gemini usage + domain (already owned). See §0.

---

## 0. Decisions & Agreed Deployment Path (2026-08-14)

Agreed with the project owner for the initial live deployment. This path anchors the rest of the document's step-by-step instructions.

| Decision | Choice | Rationale |
| :--- | :--- | :--- |
| **Compute** | Existing **Hostinger KVM 1 VPS** (1 vCPU / 4 GB / 50 GB) | Already owned — paid-for compute, no extra PaaS cost. |
| **Topology** | **Single-container** (Option B, §1) | The repo's `Dockerfile` already builds the Vite SPA into the FastAPI image (`NORAI_SPA_DIST`); one origin ⇒ zero CORS config in prod. |
| **Frontend hosting** | None separate — served by FastAPI itself | No Vercel / Cloudflare Pages needed at this scale. |
| **TLS / reverse proxy** | **Caddy** on the VPS (Let's Encrypt; Cloudflare DNS module or origin cert for Full-strict) | Simplest automatic TLS termination + renewal. |
| **DNS** | Cloudflare (free) proxy; single `A` record `app.<your-domain>` → VPS IP | Only one record needed for a single-origin deployment. |
| **Database** | **Supabase Postgres (free tier)** | Managed Postgres + daily backups; zero RAM pressure on the 4 GB VPS. |
| **Auth** | **Supabase Auth** | Already hard-wired in `backend/auth.py` (JWKS/JWT); `NORAI_DEV_INSECURE_AUTH=0` in prod. |
| **Object storage** | Local `outputs/` on a VPS volume (docker named volume) | Under 50 GB at demo scale; nightly backup job (§6.5). |

### VPS fit assessment (KVM 1 — 1 vCPU / 4 GB / 50 GB)
- **RAM**: adequate at `MAX_CONCURRENT_PIPELINES=1` (existing default, root `config.py`).
- **vCPU**: the bottleneck. `faster-whisper` + `ffmpeg` + `opencv` are CPU-bound; long-lecture transcription will be slow. Heartbeat-based stuck-protection (`PIPELINE_HEARTBEAT_INTERVAL_SEC=30`) prevents false failures. Acceptable for 4–5 demo users; upgrade to KVM 2 if it becomes the constraint.
- **Storage**: sufficient; `outputs/` is regenerable/throwaway.

### Queued pre-deploy code fixes (part of Phase 1)
1. `.env.production` is a stub — fill with real values (§5 Phase 1).
2. CORS allowlist in `backend/main.py` is localhost-only — add the prod origin.
3. `/docs` + OpenAPI is public — gate behind a prod env flag.

---

## 1. Production Architecture

NorAI consists of a **FastAPI backend** (orchestrating an 18-stage lecture processing pipeline), a **React 19 SPA frontend**, **Supabase Auth + Postgres Database**, **LangChain/ChromaDB RAG engine**, and **Google Gemini 3.1 Flash-Lite AI APIs**.

### Recommended Architecture (Decoupled vs Single-Container)

NorAI supports two production topology options:

#### Option A: Decoupled SPA + PaaS Backend (Deferred — scale-out path)
* **Frontend**: React 19 SPA deployed on **Vercel** or **Cloudflare Pages**.
* **Backend**: Dockerized FastAPI application running on **Railway**, **Render**, or a **Hetzner VPS**.
* **Database**: Managed **Supabase PostgreSQL**.
* **Authentication**: **Supabase Auth** (JWKS JWT token verification in FastAPI).
* **Storage**: **Cloudflare R2** (S3-compatible) or persistent volume mount for `outputs/`.
* **Why**: Blazing fast SPA loading via global CDN; backend scale is isolated from static asset delivery; deployment triggers for frontend and backend are completely decoupled.

#### Option B: Single-Container Deployment (AGREED PATH)
* **Frontend + Backend**: Single Docker container running FastAPI with Vite SPA built into `/app/frontend/dist` (supported out-of-the-box by NorAI's `Dockerfile` and `NORAI_SPA_DIST` environment variable).
* **Host**: **Hostinger KVM 1 VPS** (owned). Railway, Render, DigitalOcean App Platform, or Hetzner VPS remain valid alternatives if the VPS were not available.
* **Why**: Zero CORS setup; single deployment target; domain management is effortless. Matches the repo's Dockerfile exactly — no new build machinery required.

---

## 2. Domain & DNS Strategy

### Domain & Provider Requirements
* **Recommended Registrar**: Cloudflare Registrar, Namecheap, or Porkbun.
* **Suggested TLDs**: `norai.app`, `norai.ai`, `norai.study`, `norai.edu`.

### Subdomain Mapping & Environment Separation

| Environment | Frontend URL | Backend API URL | DB Instance |
| :--- | :--- | :--- | :--- |
| **Production (AGREED)** | `https://app.<your-domain>` | **same origin** (SPA served by FastAPI — no separate API subdomain) | Supabase Production DB (`norai-prod`) |
| **Staging (later)** | `https://staging.<your-domain>` | `https://api-staging.<your-domain>` (if decoupled) | Supabase Staging DB (`norai-staging`) |
| **Local Dev** | `http://localhost:5173` | `http://localhost:8000` | Local SQLite / Supabase Local Docker |

> The three-way `app`/`api`/`staging` split shown originally assumes the decoupled Option A. The agreed MVP uses **one subdomain only** (`app.<your-domain>`), because the single-container build serves SPA + API on one origin. Re-introduce `api.`/`staging.` only when moving to Option A.

### DNS & SSL Setup (Cloudflare)
1. Add custom domain to Cloudflare. Set Nameservers at your domain registrar to Cloudflare's.
2. SSL/TLS Encryption Mode: Set to **Full (strict)**.
3. Configure CNAME / A records:
   - `A app -> <VPS_IP>` (AGREED PATH; proxied via Cloudflare) — or `CNAME @ -> cname.vercel-dns.com` (Option A frontend) and `CNAME api -> railway.app` (Option A backend).
4. Enable HTTP/2, HTTP/3, and Automatic HTTPS Rewrites.

---

## 3. Hosting & Cloud Infrastructure Comparison

| Infrastructure Component | MVP / Demo (0–10 Users) | Mid-Scale (100–1,000 Users) | Enterprise (10,000+ Users) |
| :--- | :--- | :--- | :--- |
| **Frontend Hosting** | Vercel Free / Cloudflare Pages ($0/mo) | Vercel Pro ($20/mo) / Cloudflare Pages | Cloudflare Enterprise / CloudFront |
| **Backend Compute** | Railway ($5–$10/mo) / Hetzner CX22 ($4.50/mo) | Railway Pro / Hetzner CPX31 (4 vCPU, 8GB RAM - $15/mo) | AWS ECS Fargate / GCP Cloud Run / K8s |
| **Database** | Supabase Free Tier (500 MB) | Supabase Pro ($25/mo - 8GB + auto-scaling) | AWS Aurora Postgres / Managed Supabase |
| **Object Storage** | Cloudflare R2 Free (10GB) / Local VPS Disk | Cloudflare R2 ($0.015/GB) / AWS S3 | AWS S3 + CloudFront CDN |
| **Vector DB (Tutor)** | Local ChromaDB on Persistent Volume | Persistent ChromaDB / Managed Qdrant / Pinecone | Managed VectorDB (Qdrant Cloud / Pgvector) |
| **Auth** | Supabase Auth Free (50k MAU) | Supabase Auth Free/Pro | Supabase Auth / Auth0 / Clerk |

### Provider Evaluation for Backend Container

> **Agreed**: the MVP runs on the already-owned **Hostinger KVM 1 VPS** (single-container). The evaluations below are kept as reference for the case where the VPS isn't used / when scaling out.

1. **Railway (Fast MVP Launch, if not self-hosting)**:
   - **Pros**: Direct GitHub integration, automatic Docker builds, persistent volume support, zero server setup, easy env management.
   - **Cons**: $5 minimum project cost after trial.
2. **Hetzner Cloud VPS / any bare VPS (Cost & CPU Performance)**:
   - **Pros**: CX22 instance (2 vCPU, 4 GB RAM, 40 GB NVMe) for only **€4.50/mo (~$5.00)**. Blazing fast CPU performance for `faster-whisper` and `ffmpeg`. The user's Hostinger KVM 1 is the same class of infra, just with a single vCPU — same manual-Docker-Compose + reverse-proxy workflow applies.
   - **Cons**: Requires manual Docker Compose setup, Caddy reverse proxy, and basic Linux administration.
3. **Render**:
   - **Pros**: Good UI, smooth Git workflow.
   - **Cons**: Free tier sleeps after 15 mins (unusable for long pipelines); 2 GB RAM instance costs $14/mo.
4. **AWS / GCP**:
   - **Pros**: Infinite scaling.
   - **Cons**: Severe complexity, IAM overhead, unpredictable billing for early MVP stage.

---

## 4. Financial Cost Projections

> **Agreed-path adjustment**: backend compute is the already-owned Hostinger VPS, so deduct the "Backend Compute" line from every scenario below until the VPS is replaced/upgraded or extra capacity is added.

### Detailed Monthly Cost Breakdown by User Scale

```
Cost ($)
  |                                                                   [1,000 Users]
  |                                                                   ~$310/mo
  |                                                                     /
  |                                                  [100 Users]       /
  |                                                   ~$42/mo         /
  |                                                     /            /
  |                        [5-10 Users]                /            /
  |                          ~$8/mo                   /            /
  |                            /                     /            /
  +---------------------------+---------------------+------------+---------->
                           MVP Stage             Mid-Scale      Scale-up
```

#### Scenario 1: 0 Users (Idle / Idle Staging)
* **Domain**: $1.00/mo
* **Frontend (Vercel/CF Pages)**: $0.00
* **Backend (Railway/Hetzner)**: $5.00/mo
* **Database (Supabase Free)**: $0.00
* **Storage (R2/VPS Disk)**: $0.00
* **Gemini API**: $0.00
* **Total**: **~$6.00 / month**

#### Scenario 2: 5–10 Demo Users (50 Lectures processed/mo ~ 30 mins each)
* **Domain**: $1.00/mo
* **Frontend**: $0.00
* **Backend Compute**: $5.00 – $7.00/mo (1 worker, 2-4 GB RAM)
* **Database**: $0.00 (Supabase Free Tier)
* **Storage (Cloudflare R2)**: $0.00 (under 10 GB)
* **Gemini API Usage**:
  * 50 lectures * 15 chunks = 750 LLM calls.
  * ~3M input tokens + 0.5M output tokens = **~$1.50/mo**.
* **Total**: **~$7.50 – $9.50 / month**

#### Scenario 3: 100 Active Users (500 Lectures processed/mo ~ 45 mins each)
* **Domain**: $1.00/mo
* **Frontend**: $0.00 – $20.00/mo (Vercel Free or Pro)
* **Backend Compute**: $15.00/mo (Hetzner CPX31 4 vCPU / 8 GB RAM or 2x Railway instances)
* **Database**: $0.00 – $25.00/mo (Supabase Free or Pro)
* **Storage (R2 50 GB)**: $0.60/mo
* **Gemini API Usage**: ~30M input tokens + 5M output tokens = **~$15.00/mo**.
* **Total**: **~$31.60 – $61.60 / month**

#### Scenario 4: 1,000 Active Users (5,000 Lectures processed/mo)
* **Domain & CDN**: $5.00/mo
* **Frontend**: $20.00/mo (Vercel Pro)
* **Backend Compute Cluster**: $60.00/mo (Autoscaled worker instances)
* **Database**: $25.00/mo (Supabase Pro with Compute Addon)
* **Storage (R2 500 GB)**: $7.50/mo
* **Gemini API Usage**: ~300M input tokens + 50M output tokens = **~$150.00/mo**.
* **Monitoring & Mail**: $40.00/mo
* **Total**: **~$307.50 / month**

---

## 5. Comprehensive Step-by-Step Deployment Tutorial

### Phase 1: Codebase Preparation & Build Verification

#### 1. Audit Environment Variables
Create `.env.production` on backend deployment target:

```ini
# Production API Keys
GEMINI_API_KEY=AIzaSy...your_gemini_api_key

# Supabase Production Config
SUPABASE_URL=https://xyzyourproject.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOi...
SUPABASE_JWT_SECRET=your-supabase-jwt-secret
DATABASE_URL=postgresql+asyncpg://postgres:[YOUR-PASSWORD]@db.xyzyourproject.supabase.co:5432/postgres

# Frontend & CORS Config
# Single-container / same-origin: leave VITE_API_BASE_URL EMPTY so the SPA uses
# relative paths against the same origin (frontend/src/lib/http.ts). Set it only
# if you move to the decoupled Option A.
VITE_API_BASE_URL=
VITE_SUPABASE_URL=https://xyzyourproject.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGciOi...

# Billing (Lemon Squeezy)
LEMONSQUEEZY_WEBHOOK_SECRET=whsec_...
LEMONSQUEEZY_CHECKOUT_STARTER_URL=https://norai.lemonsqueezy.com/buy/...
LEMONSQUEEZY_CHECKOUT_PRO_URL=https://norai.lemonsqueezy.com/buy/...
LEMONSQUEEZY_CUSTOMER_PORTAL_URL=https://norai.lemonsqueezy.com/billing

# Pipeline Settings
NORAI_DEV_INSECURE_AUTH=0
NORAI_WHISPER_MODEL=small
MAX_FREE_DURATION_MIN=15
```

#### 2. Run Database Migrations via Alembic
Before launching the backend, run Alembic migrations against the production database:

```bash
# Set production DATABASE_URL
export DATABASE_URL="postgresql+asyncpg://postgres:PASSWORD@db.xyz.supabase.co:5432/postgres"

# Execute migrations to head
venv/bin/alembic upgrade head
```

#### 3. Test Production Docker Container Locally
Verify the single-container image builds cleanly:

```bash
# Build image
docker build -t norai-app:latest .

# Run container locally with production env flags
docker run -d --name norai_prod_test \
  -p 8000:8000 \
  --env-file .env \
  norai-app:latest

# Verify health endpoint
curl -I http://localhost:8000/docs
```

#### 4. Apply the queued pre-deploy code fixes (§0)
1. **CORS**: in `backend/main.py`, add the prod origin (`https://app.<your-domain>`) to the `allow_origins` list while keeping the localhost dev entries.
2. **Gate `/docs`**: disable the OpenAPI routes (`docs_url=None, redoc_url=None, openapi_url=None`) unless an env flag (e.g. `NORAI_ENV != "production"`) is set, so Swagger is not public in prod.

---

### Phase 2: Cloud Infrastructure & Database Setup

#### 1. Setup Supabase Project
1. Create a project at [supabase.com](https://supabase.com).
2. Go to **Project Settings -> API** to copy `SUPABASE_URL`, `anon key`, and `JWT Secret`.
3. Go to **Authentication -> Providers** and configure Email/Password or Google OAuth.
4. Go to **Database -> Connection String** and copy the URI (`postgresql://postgres:[password]@db.[ref].supabase.co:5432/postgres`).

#### 2. Deploy Single-Container to the VPS (AGREED PATH)
1. SSH into the Hostinger KVM 1 VPS.
2. Install Docker + docker-compose plugin (official convenience scripts) and **Caddy**.
3. Clone/push the repo onto the VPS (e.g. `/srv/norai`).
4. Create `/srv/norai/.env` from the `.env.production` values.
5. Run the single container with the outputs volume mounted:
   ```bash
   docker compose up --build -d
   ```
   (`docker-compose.yml` already mounts the `norai_outputs` volume at `/app/outputs`.)
6. Point Caddy at the container: reverse-proxy `app.<your-domain>` → `http://127.0.0.1:8000`; use the Cloudflare DNS module or an origin cert for Let's Encrypt under Cloudflare proxy (Full-strict).
7. Verify: `curl https://app.<your-domain>/docs` returns 200.

#### 3. Deploy Frontend SPA (Option A: Vercel) — NOT used in the agreed path
1. Import repository on [Vercel](https://vercel.com).
2. Set Root Directory to `frontend`.
3. Framework Preset: **Vite**.
4. Configure Build Command: `npm run build`, Output Directory: `dist`.
5. Set Environment Variables:
   - `VITE_API_BASE_URL=https://api.<your-domain>` (or Railway backend URL)
   - `VITE_SUPABASE_URL=https://xyz.supabase.co`
   - `VITE_SUPABASE_ANON_KEY=eyJ...`
6. Deploy!

#### 4. Deploy Backend Container (Option A: Railway) — NOT used in the agreed path
1. Log in to [Railway.app](https://railway.app) and create a new project from your GitHub Repository.
2. Select the Dockerfile build strategy.
3. Add environment variables listed in `.env.production`.
4. Add a **Persistent Volume** mounted to `/app/outputs` (Size: 10 GB).
5. Generate a public domain (e.g. `norai-backend-production.up.railway.app`).

---

### Phase 3: CI/CD Pipeline (GitHub Actions)

Create `.github/workflows/deploy.yml` for automated testing and deployment:

```yaml
name: NorAI Production CI/CD

on:
  push:
    branches: [ main ]

jobs:
  lint-and-build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: 20
          
      - name: Lint Frontend
        run: |
          cd frontend
          npm ci
          npm run lint
          npm run build

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Validate Backend Syntax & Importability
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          python -c "import backend.main; print('Backend loaded successfully')"

  deploy-vps:
    needs: lint-and-build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to VPS (SSH)
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.VPS_HOST }}
          username: ${{ secrets.VPS_USER }}
          key: ${{ secrets.VPS_SSH_KEY }}
          script: |
            cd /srv/norai
            git pull
            docker compose up --build -d
```

> Alternative (not the agreed path): a `bervProject/railway-deploy@main` job using `secrets.RAILWAY_TOKEN` if the backend moves to Railway. The repo's existing `.github/workflows/ci.yml` already covers the `lint-and-build` half; this deploy job extends it.

---

## 6. Security, Governance & Production Readiness

### 1. Authentication & JWT Security
* **JWT Verification**: Handled in `backend/auth.py` via Supabase JWKS public keys. Ensure `NORAI_DEV_INSECURE_AUTH` is **0** in production.
* **Token Expiration**: Set Supabase Access Token TTL to 3600s (1 hour) with automatic refresh.

### 2. CORS & Network Security
* In `backend/main.py`, configure CORS explicitly for production domains:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://app.<your-domain>",      # agreed prod origin
        # keep the localhost dev origins, add Option-A origins if ever split
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

> With the single-container path, browser requests to the API are **same-origin**, so CORS is effectively moot in prod — but keep the list explicit and minimal anyway. Also gate `/docs`/OpenAPI behind a non-production env flag (§5 Phase 1, step 4).

### 3. Rate Limiting & API Abuse Prevention
* NorAI includes built-in rate limiting (`backend/ratelimit.py`) and billing quota verification (`backend/auth.py` & `backend/db/models.py`).
* Enforce maximum upload sizes (`NORAI_MAX_UPLOAD_BYTES=2147483648` -> 2GB).
* Cloudflare WAF: Enable Rate Limiting rules on `/api/*` endpoints (e.g. max 100 req/min per IP).

### 4. Database Security & Connection Pooling
* Use Supabase Transaction Pooler (port 6543) for high concurrency if needed.
* Restrict Postgres access: Ensure direct DB ports are not exposed publicly without password enforcement.

### 5. Automated Backups & Disaster Recovery
* **Database**: Supabase takes automated daily snapshots. Enable Point-in-Time Recovery (PITR) when scaling.
* **Outputs Storage**: Sync persistent `outputs/` directory or Cloudflare R2 bucket nightly using `rclone` or AWS CLI.

---

## 7. Execution Checkpoints & Definition of Done

Use these 9 sequential checkpoints to execute and verify the deployment step by step.

### Checkpoint 0: Codebase & Build Readiness
* **What to do**: Run oxlint, verify Vite SPA build, run local Docker build test.
* **Verification**: `npm run lint` passes without errors; `docker build -t norai-app .` succeeds locally.
* **Definition of Done**: Clean Docker container image generated locally.

### Checkpoint 1: Production Infrastructure & Accounts
* **What to do**: Provision Supabase project, Cloudflare account, Hostinger VPS (already owned).
* **Verification**: Connect to Supabase DB via `psql` or Supabase Dashboard; Cloudflare nameservers active; SSH into the VPS works.
* **Definition of Done**: All cloud accounts active and API tokens created.

### Checkpoint 2: Database Schema & Migration
* **What to do**: Execute `alembic upgrade head` against Supabase Postgres.
* **Verification**: Inspect table schema in Supabase Table Editor (`users`, `subscriptions`, `lectures`, `usage_logs`, `courses`, `share_links`, `webhook_events`).
* **Definition of Done**: Postgres tables created cleanly with correct indices and foreign keys.

### Checkpoint 3: Backend Deployment (VPS)
* **What to do**: Deploy the single-container image to the Hostinger VPS (`docker compose up --build -d`) with the `norai_outputs` volume mounted at `/app/outputs`.
* **Verification**: `curl https://app.<your-domain>/docs` returns 200 OK OpenAPI UI.
* **Definition of Done**: Backend online, processing pipeline dependencies (`faster-whisper`, `ffmpeg`, `opencv`) functional.

### Checkpoint 4: Frontend Deployment
* **What to do**: SPA is served by the same container (no separate deploy). Verify the full origin loads.
* **Verification**: Load `https://app.<your-domain>/` in browser, inspect console for 0 CORS errors.
* **Definition of Done**: SPA rendered cleanly on the custom domain.

### Checkpoint 5: Authentication & User Sync
* **What to do**: Register a test user via Supabase Auth on the frontend.
* **Verification**: Check `users` and `subscriptions` tables in Supabase to confirm new user row was auto-provisioned by `get_or_create_user_from_token`.
* **Definition of Done**: User login, JWT decoding, and DB provisioning verified end-to-end.

### Checkpoint 6: End-to-End Pipeline Smoke Test
* **What to do**: Upload a 5-minute demo video/audio file or YouTube link.
* **Verification**: Pipeline progresses through Ingestion -> Transcription -> Extraction -> Notes -> Flashcards -> Tutor indexing. Check output files in `/app/outputs`.
* **Definition of Done**: Full 18-stage pipeline completes successfully in production.

### Checkpoint 7: Security & Rate Limiting Audit
* **What to do**: Attempt unauthenticated requests, check SSL grade on SSLLabs, verify CORS policies.
* **Verification**: SSLLabs gives Grade A+; invalid JWTs return 401 Unauthorized; non-whitelisted origins fail CORS.
* **Definition of Done**: Production endpoints locked down and secured.

### Checkpoint 8: Production Launch & Monitoring
* **What to do**: Enable Uptime monitoring (Better Stack / GlitchTip) and launch demo to the 4-5 initial testers.
* **Verification**: Monitor logs via `docker logs` on the VPS during tester sessions.
* **Definition of Done**: Live SaaS product accessible to public demo users.

---

## Recommended Step-by-Step Implementation Sequence (AGREED PATH)

1. **Step 1**: Fill `.env.production` with real values; apply CORS + `/docs` gating fixes (Phase 1); verify `docker build -t norai-app .` locally.
2. **Step 2**: Create free project on Supabase; obtain DB string + Auth keys.
3. **Step 3**: Run `alembic upgrade head` to set up production database schema.
4. **Step 4**: Point `app.<your-domain>` `A` record at the Hostinger VPS behind Cloudflare proxy; set SSL mode Full (strict).
5. **Step 5**: Install Docker + Caddy on the VPS; clone the repo; run `docker compose up --build -d` with the real `.env`.
6. **Step 6**: Configure Caddy reverse proxy → `http://127.0.0.1:8000` (Cloudflare DNS module / origin cert) so `https://app.<your-domain>` terminates TLS.
7. **Step 7**: Perform end-to-end lecture processing test with test account (register → upload short video → pipeline completes).
8. **Step 8**: Harden (gate `/docs`, tighten CORS), schedule nightly `outputs/` backups, enable uptime monitoring, hand over login credentials to the 4–5 initial demo users.

> Scaling-out triggers (later, not now): split to Option A (Vercel + API subdomain), move Postgres to Supabase Pro / dedicated, and add a second vCPU worker for transcription.
