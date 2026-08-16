# NorAI — End-to-End Production Deployment & Infrastructure Guide

This document provides a comprehensive, project-specific, and practical deployment strategy for taking **NorAI** from local development (`localhost`) to a public, production-ready SaaS on your **Hostinger KVM 1 VPS** under your custom subdomain.

---

## Executive Summary & Target Production Stack

```
                      +------------------------------------------+
                      |         Cloudflare (DNS & SSL)           |
                      |        app.yourdomain.com (Proxied)      |
                      +--------------------+---------------------+
                                           | HTTPS (Full-strict)
                                           v
                      +------------------------------------------+
                      |       Hostinger KVM 1 VPS (Ubuntu)       |
                      |  +------------------------------------+  |
                      |  |     Caddy Web Server (TLS Proxy)   |  |
                      |  +-----------------+------------------+  |
                      |                    | http://127.0.0.1:8000
                      |                    v
                      |  +------------------------------------+  |
                      |  | Docker: NorAI Single-Container     |  |
                      |  |   - FastAPI (API & WebSocket)      |  |
                      |  |   - React 19 SPA (/frontend/dist)  |  |
                      |  |   - Gemini Cloud ASR & FFmpeg      |  |
                      |  |   - LangChain & ChromaDB RAG Tutor |  |
                      |  +-----------------+------------------+  |
                      |                    | Local Volume Mount  |
                      |                    v                     |
                      |     /outputs (ChromaDB, Artifacts)       |
                      +--------------------+---------------------+
                                           | (SQLAlchemy / asyncpg)
                                           v
                      +------------------------------------------+
                      |          Supabase Managed Cloud          |
                      |  - PostgreSQL Database (Tables & Quotas) |
                      |  - Supabase Auth (JWT & JWKS Validation) |
                      +------------------------------------------+
```

### Initial Monthly Cost (MVP Stage)

| Service | Provider & Plan | Est. Monthly Cost | Notes |
| :--- | :--- | :--- | :--- |
| **Backend & Frontend** | Hostinger KVM 1 VPS (Owned) | **$0.00 additional** | 1 vCPU / 4 GB RAM / 50 GB NVMe (Already owned) |
| **Domain & DNS** | Custom Domain + Cloudflare CDN | **$1.00 – $2.50 / mo** | Free SSL, DDoS mitigation, Global CDN |
| **Database & Auth** | Supabase Free Tier | **$0.00** | 500 MB PostgreSQL, 50k MAU Auth, daily backups |
| **AI LLM & Vision** | Google Gemini API (`gemini-3.1-flash-lite`) | **$0.50 – $3.00** | Pay-as-you-go ($0.25/1M in, $1.50/1M out, audio ASR) |
| **Reverse Proxy** | Caddy (Open Source) | **$0.00** | Automatic Let's Encrypt TLS termination |
| **TOTAL MONTHLY COST** | | **~$1.50 – $4.50 / month** | |

---

## 1. Finalized & Seeded 3 Demo Video Workspaces

The 3 high-impact educational video workspaces have been processed, tested, and bundled into `seed_data/`:

| # | Domain & Video Title | Lecture ID | Key Features Showcased |
| :--- | :--- | :--- | :--- |
| **Demo 1** | **Computer Science & Deep Learning**<br>*Foundations of Neural Networks & Deep Learning* | `ab648382-638f-4dde-b7c1-4007a2e638bb` | • LaTeX/KaTeX equation derivations (matrix weights $W$, bias $b$, Sigmoid vs ReLU)<br>• 4 comprehensive chapters with parameterization tables<br>• 3D Interactive Flashcards & Socratic Nora AI Tutor |
| **Demo 2** | **Economics & Market Theory**<br>*Foundations of Economic Thinking: Incentives and Opportunity Cost* | `e54d7376-0e7b-472a-9ca6-9b21ad0b2710` | • 6 rich chapters (Price Signals, Supply/Demand Distortions, Capital Flight)<br>• Comparative tables & structured revision cheat-sheet<br>• Practice Assessment & Chapter-grounded RAG Tutor |
| **Demo 3** | **Modern AI Engineering**<br>*The Rise of Open-Weights Models and Local Deployment* | `506dd685-05f9-43df-8d09-5b944c7392f5` | • Hardware VRAM formulas & Dynamic Quantization calculations<br>• 3 structured chapters (Open-Weights vs Frontier, Memory Math)<br>• Instant 1-Click Launch with zero signup requirement |

> [!TIP]
> **Zero Footprint**: All 3 seeded demo workspaces combined take only **36 MB** on disk, including all keyframe screenshots, Chroma vector databases, notes, and quiz evaluations. They are bundled in `seed_data/` and automatically hydrated into `outputs/` upon container startup.

---

## 2. Access Control & Freemium Strategy

### A. 3 Permanent Public Demo Workspaces
- **Zero Friction**: The 3 seeded demo lectures are permanently accessible without requiring login or signup.
- **Full Interactivity**: Visitors can browse the Study Notes, view the slide screenshots, flip 3D Flashcards, test themselves with Assessments, and chat with Nora (AI Tutor).
- **Zero Quota Consumption**: Exploring demo workspaces does not consume user processing quota.
- **Backend Exemption**: `ensure_lecture_access()` in `backend/main.py` permits access to the demo lecture IDs for all users.

### B. Free User Processing Limit (15 Minutes)
- **Duration Cap**: Enforced by `MAX_FREE_DURATION_MIN=15`.
- **Pre-flight & Post-download Gates**: Videos under 15 minutes process for free; longer videos prompt the user that the free trial limit is 15 minutes.

### C. Future Monetization: Razorpay Integration Path
- Replaces Lemon Squeezy with **Razorpay**:
  1. **Orders API**: Backend endpoint `POST /billing/razorpay/create-order` creates an order with receipt and plan details.
  2. **Frontend Checkout**: Standard Razorpay modal popup (`Razorpay(options).open()`).
  3. **Webhook Verification**: `POST /webhooks/razorpay` verifies HMAC-SHA256 signature using `RAZORPAY_WEBHOOK_SECRET` and upgrades the user's row in the `subscriptions` table.

---

## 3. End-to-End VPS Deployment Checklist

### Phase 1: Code Readiness & Pre-Deploy Hardening (Local Repo) — [COMPLETED]

- [x] **1.1 CORS Production Origin**:
  Updated `backend/main.py` to support `NORAI_ALLOWED_ORIGINS` (comma-separated list of production domains) plus automatic `RENDER_EXTERNAL_URL` support:
  ```python
  cors_origins = [
      "http://localhost:5173",
      "http://127.0.0.1:5173",
      "http://localhost:3000",
      "http://127.0.0.1:3000",
      "http://localhost:4173",
      "http://127.0.0.1:4173",
      "http://localhost:8000",
      "http://127.0.0.1:8000",
  ]
  if extra_origins := os.environ.get("NORAI_ALLOWED_ORIGINS"):
      cors_origins.extend([o.strip() for o in extra_origins.split(",") if o.strip()])
  if render_url := os.environ.get("RENDER_EXTERNAL_URL"):
      cors_origins.append(render_url.strip())
  ```
- [x] **1.2 Gate OpenAPI / Swagger in Production**:
  Gated `/docs`, `/redoc`, and `/openapi.json` behind `NORAI_ENV=production`:
  ```python
  is_prod = os.environ.get("NORAI_ENV") == "production"
  app = FastAPI(
      title="NorAI Tutor API",
      lifespan=lifespan,
      docs_url=None if is_prod else "/docs",
      redoc_url=None if is_prod else "/redoc",
      openapi_url=None if is_prod else "/openapi.json",
  )
  ```
- [x] **1.3 Demo Lecture Access & Startup Sync**:
  Bundled 3 demo lectures into `seed_data/`, added `sync_demo_seed_data()` in FastAPI `lifespan`, and granted universal public access in `ensure_lecture_access()`.
- [x] **1.4 Verified Single-Container Dockerfile & Requirements**:
  Multi-stage `Dockerfile` (Node 20 Alpine for Vite React build + Python 3.12 slim with exact-pinned `requirements.txt`) configured and validated.
- [x] **1.5 Production Environment Template**:
  Updated `.env.example` with `NORAI_ENV`, `NORAI_ALLOWED_ORIGINS`, and Razorpay placeholders.

---

### Phase 2: Database & Auth Setup (Supabase)

- [ ] **2.1 Create Supabase Project**:
  1. Sign in to [supabase.com](https://supabase.com) and create a new project.
  2. Copy `SUPABASE_URL`, `anon key`, and `JWT Secret` from **Project Settings → API**.
  3. Copy the Connection URI from **Database → Connection Pooling** (`postgresql+asyncpg://postgres:[password]@db.[ref].supabase.co:5432/postgres`).
- [ ] **2.2 Run Alembic Migrations**:
  ```bash
  export DATABASE_URL="postgresql+asyncpg://postgres:YOUR_PASSWORD@db.YOUR_REF.supabase.co:5432/postgres"
  venv/bin/alembic upgrade head
  ```
  Verify the tables (`users`, `subscriptions`, `lectures`, `usage_logs`, `courses`, `share_links`, `webhook_events`) in the Supabase Dashboard.

---

### Phase 3: Cloudflare DNS & SSL Configuration

- [ ] **3.1 DNS Record**:
  - Add an `A` record in Cloudflare:
    - **Name**: `app` (or your chosen subdomain)
    - **IPv4 Address**: `<HOSTINGER_VPS_IP>`
    - **Proxy status**: **Proxied** (Orange Cloud icon enabled)
- [ ] **3.2 SSL/TLS Settings**:
  - In Cloudflare dashboard, go to **SSL/TLS** → set encryption mode to **Full (strict)** or **Full**.
  - Enable **Always Use HTTPS** and **HTTP/2 & HTTP/3**.

---

### Phase 4: Hostinger VPS Setup (Docker + Caddy)

- [ ] **4.1 SSH into VPS & Update Packages**:
  ```bash
  ssh root@<YOUR_VPS_IP>
  apt-get update && apt-get upgrade -y
  ```
- [ ] **4.2 Install Docker Engine & Compose**:
  ```bash
  curl -fsSL https://get.docker.com -o get-docker.sh
  sh get-docker.sh
  docker --version && docker compose version
  ```
- [ ] **4.3 Install Caddy Web Server**:
  ```bash
  sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
  sudo apt update && sudo apt install caddy -y
  ```
- [ ] **4.4 Configure `/etc/caddy/Caddyfile`**:
  ```caddy
  app.yourdomain.com {
      reverse_proxy 127.0.0.1:8000
      encode gzip zstd
      
      header {
          Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
          X-Content-Type-Options "nosniff"
          X-Frame-Options "DENY"
          Referrer-Policy "strict-origin-when-cross-origin"
      }
  }
  ```
  Reload Caddy:
  ```bash
  sudo systemctl reload caddy
  ```

---

### Phase 5: Clone, Configure & Deploy Single-Container App

- [ ] **5.1 Clone Repository to `/srv/norai`**:
  ```bash
  git clone <YOUR_GIT_REPO_URL> /srv/norai
  cd /srv/norai
  ```
- [ ] **5.2 Create Production `/srv/norai/.env`**:
  ```ini
  # Core AI & Runtime
  GEMINI_API_KEY=AIzaSy...
  NORAI_ENV=production
  NORAI_TRANSCRIPTION_BACKEND=gemini
  MAX_FREE_DURATION_MIN=15
  NORAI_DEV_ACCESS=0
  NORAI_DEV_INSECURE_AUTH=0

  # Supabase Database & Auth
  DATABASE_URL=postgresql+asyncpg://postgres:PASSWORD@db.REF.supabase.co:5432/postgres
  SUPABASE_URL=https://REF.supabase.co
  SUPABASE_ANON_KEY=eyJ...
  SUPABASE_JWT_SECRET=YOUR_SUPABASE_JWT_SECRET

  # Frontend Build-time Settings
  VITE_API_BASE_URL=
  VITE_SUPABASE_URL=https://REF.supabase.co
  VITE_SUPABASE_ANON_KEY=eyJ...

  # Future Razorpay Config
  RAZORPAY_KEY_ID=
  RAZORPAY_KEY_SECRET=
  RAZORPAY_WEBHOOK_SECRET=
  ```
- [ ] **5.3 Launch the Application**:
  ```bash
  docker compose up --build -d
  ```
  Verify running status:
  ```bash
  docker compose ps
  docker compose logs -f app
  ```

---

### Phase 6: Seed the 3 Demo Lectures & Verify

- [ ] **6.1 Process the 3 Demo Lectures**:
  Run the 3 chosen demo videos through the pipeline (either by processing them on the live instance or copying local `outputs/` data to the VPS `norai_outputs` docker volume):
  ```bash
  # Example copying local outputs to VPS
  rsync -avz outputs/<demo-lecture-id> root@<VPS_IP>:/var/lib/docker/volumes/norai_norai_outputs/_data/
  ```
- [ ] **6.2 Smoke Test**:
  1. Open `https://app.yourdomain.com` in your browser.
  2. Verify that the 3 demo lectures load immediately with full notes, flashcards, assessments, and AI Tutor chat without requiring login.
  3. Test processing a short video (<15 min) with a free registered account.
  4. Verify that videos >15 min display the free-trial duration limit notice.

---

## 4. Production Maintenance & Operations

- **Logs Inspection**: `docker compose logs --tail=100 -f app`
- **Restarting Service**: `docker compose restart app`
- **Updating to New Version**:
  ```bash
  cd /srv/norai
  git pull
  docker compose up --build -d
  ```
- **Automated Outputs Backup**: Schedule a cron job to sync `/var/lib/docker/volumes/norai_norai_outputs/_data` to a secondary storage (Cloudflare R2, Google Drive, or local machine) weekly.
