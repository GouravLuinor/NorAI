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

---

## 1. Production Architecture

NorAI consists of a **FastAPI backend** (orchestrating an 18-stage lecture processing pipeline), a **React 19 SPA frontend**, **Supabase Auth + Postgres Database**, **LangChain/ChromaDB RAG engine**, and **Google Gemini 3.1 Flash-Lite AI APIs**.

### Recommended Architecture (Decoupled vs Single-Container)

NorAI supports two production topology options:

#### Option A: Decoupled SPA + PaaS Backend (Recommended for Web SaaS)
* **Frontend**: React 19 SPA deployed on **Vercel** or **Cloudflare Pages**.
* **Backend**: Dockerized FastAPI application running on **Railway**, **Render**, or a **Hetzner VPS**.
* **Database**: Managed **Supabase PostgreSQL**.
* **Authentication**: **Supabase Auth** (JWKS JWT token verification in FastAPI).
* **Storage**: **Cloudflare R2** (S3-compatible) or persistent volume mount for `outputs/`.
* **Why**: Blazing fast SPA loading via global CDN; backend scale is isolated from static asset delivery; deployment triggers for frontend and backend are completely decoupled.

#### Option B: Single-Container Deployment (Simplest Operations)
* **Frontend + Backend**: Single Docker container running FastAPI with Vite SPA built into `/app/frontend/dist` (supported out-of-the-box by NorAI's `Dockerfile` and `NORAI_SPA_DIST` environment variable).
* **Host**: **Railway**, **Render**, **DigitalOcean App Platform**, or **Hetzner VPS**.
* **Why**: Zero CORS setup; single deployment target; domain management is effortless.

---

## 2. Domain & DNS Strategy

### Domain & Provider Requirements
* **Recommended Registrar**: Cloudflare Registrar, Namecheap, or Porkbun.
* **Suggested TLDs**: `norai.app`, `norai.ai`, `norai.study`, `norai.edu`.

### Subdomain Mapping & Environment Separation

| Environment | Frontend URL | Backend API URL | DB Instance |
| :--- | :--- | :--- | :--- |
| **Production** | `https://app.norai.ai` (or `https://norai.ai`) | `https://api.norai.ai` | Supabase Production DB (`norai-prod`) |
| **Staging** | `https://staging.norai.ai` | `https://api-staging.norai.ai` | Supabase Staging DB (`norai-staging`) |
| **Local Dev** | `http://localhost:5173` | `http://localhost:8000` | Local SQLite / Supabase Local Docker |

### DNS & SSL Setup (Cloudflare)
1. Add custom domain to Cloudflare. Set Nameservers at your domain registrar to Cloudflare's.
2. SSL/TLS Encryption Mode: Set to **Full (strict)**.
3. Configure CNAME / A records:
   - `CNAME @ -> cname.vercel-dns.com` (or Cloudflare Pages target)
   - `CNAME api -> railway.app` (or server IP `A api -> 1.2.3.4`)
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

1. **Railway (Top Recommendation for Fast MVP Launch)**:
   - **Pros**: Direct GitHub integration, automatic Docker builds, persistent volume support, zero server setup, easy env management.
   - **Cons**: $5 minimum project cost after trial.
2. **Hetzner Cloud VPS (Top Recommendation for Cost & CPU Performance)**:
   - **Pros**: CX22 instance (2 vCPU, 4 GB RAM, 40 GB NVMe) for only **€4.50/mo (~$5.00)**. Blazing fast CPU performance for `faster-whisper` and `ffmpeg`.
   - **Cons**: Requires manual Docker Compose setup, Caddy reverse proxy, and basic Linux administration.
3. **Render**:
   - **Pros**: Good UI, smooth Git workflow.
   - **Cons**: Free tier sleeps after 15 mins (unusable for long pipelines); 2 GB RAM instance costs $14/mo.
4. **AWS / GCP**:
   - **Pros**: Infinite scaling.
   - **Cons**: Severe complexity, IAM overhead, unpredictable billing for early MVP stage.

---

## 4. Financial Cost Projections

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
VITE_API_BASE_URL=https://api.norai.ai
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

---

### Phase 2: Cloud Infrastructure & Database Setup

#### 1. Setup Supabase Project
1. Create a project at [supabase.com](https://supabase.com).
2. Go to **Project Settings -> API** to copy `SUPABASE_URL`, `anon key`, and `JWT Secret`.
3. Go to **Authentication -> Providers** and configure Email/Password or Google OAuth.
4. Go to **Database -> Connection String** and copy the URI (`postgresql://postgres:[password]@db.[ref].supabase.co:5432/postgres`).

#### 2. Deploy Backend Container (Option A: Railway)
1. Log in to [Railway.app](https://railway.app) and create a new project from your GitHub Repository.
2. Select the Dockerfile build strategy.
3. Add environment variables listed in `.env.production`.
4. Add a **Persistent Volume** mounted to `/app/outputs` (Size: 10 GB).
5. Generate a public domain (e.g. `norai-backend-production.up.railway.app`).

#### 3. Deploy Frontend SPA (Option A: Vercel)
1. Import repository on [Vercel](https://vercel.com).
2. Set Root Directory to `frontend`.
3. Framework Preset: **Vite**.
4. Configure Build Command: `npm run build`, Output Directory: `dist`.
5. Set Environment Variables:
   - `VITE_API_BASE_URL=https://api.norai.ai` (or Railway backend URL)
   - `VITE_SUPABASE_URL=https://xyz.supabase.co`
   - `VITE_SUPABASE_ANON_KEY=eyJ...`
6. Deploy!

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

  deploy-railway:
    needs: lint-and-build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to Railway
        uses: bervProject/railway-deploy@main
        with:
          railway_token: ${{ secrets.RAILWAY_TOKEN }}
          service: "norai-backend"
```

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
        "https://norai.ai",
        "https://app.norai.ai",
        "https://staging.norai.ai",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

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
* **What to do**: Provision Supabase project, Cloudflare account, Railway/Hetzner server instance.
* **Verification**: Connect to Supabase DB via `psql` or Supabase Dashboard; Cloudflare nameservers active.
* **Definition of Done**: All cloud accounts active and API tokens created.

### Checkpoint 2: Database Schema & Migration
* **What to do**: Execute `alembic upgrade head` against Supabase Postgres.
* **Verification**: Inspect table schema in Supabase Table Editor (`users`, `subscriptions`, `lectures`, `usage_logs`, `courses`, `share_links`, `webhook_events`).
* **Definition of Done**: Postgres tables created cleanly with correct indices and foreign keys.

### Checkpoint 3: Backend Deployment
* **What to do**: Deploy Docker container to Railway/Hetzner. Mount `/app/outputs` persistent volume.
* **Verification**: `curl https://api.norai.ai/docs` returns 200 OK OpenAPI UI.
* **Definition of Done**: Backend online, processing pipeline dependencies (`faster-whisper`, `ffmpeg`, `opencv`) functional.

### Checkpoint 4: Frontend Deployment
* **What to do**: Deploy SPA to Vercel/Cloudflare Pages with `VITE_API_BASE_URL` pointing to backend API.
* **Verification**: Load frontend URL in browser, inspect console for 0 CORS errors.
* **Definition of Done**: Frontend SPA rendered cleanly on custom domain.

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
* **Verification**: Monitor logs via `docker logs` / Railway log viewer during tester sessions.
* **Definition of Done**: Live SaaS product accessible to public demo users.

---

## Recommended Step-by-Step Implementation Sequence

1. **Step 1**: Register domain on Cloudflare/Namecheap (`$10/yr`).
2. **Step 2**: Create free project on Supabase, obtain DB string + Auth keys.
3. **Step 3**: Run `alembic upgrade head` to set up production database schema.
4. **Step 4**: Deploy backend Docker image to Railway ($5/mo) or Hetzner VPS ($5/mo).
5. **Step 5**: Deploy frontend SPA to Vercel (Free) or Cloudflare Pages (Free).
6. **Step 6**: Configure DNS A/CNAME records in Cloudflare.
7. **Step 7**: Perform end-to-end lecture processing test with test account.
8. **Step 8**: Hand over login credentials to the 4–5 initial demo users!
