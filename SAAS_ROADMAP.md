# NorAI — Production Micro-SaaS Foundation: Decision Roadmap

**Scope**: Landing page, auth, DB migration, free trial, payments, pricing tiers + quotas.
**Base Architecture**: FastAPI backend (`backend/main.py`, `backend/orchestrator.py`) + React 19 / TypeScript Vite SPA (`frontend/`). SQLite storage (`outputs/<id>/tutor/checkpoints.sqlite` + `outputs/lectures.json`). Model defaults: `gemini-3.1-flash-lite`.

---

## Executive Overview & Topology Decision (Q1)

- **Workspace Topology**: Unified Vite + React 19 SPA (`frontend/`) for both marketing/landing and workspace dashboard. 
- **Database & Auth**: Supabase Postgres + Supabase Auth (Postgres-native user tables, JWT-based backend verification).
- **Payment Merchant of Record**: Lemon Squeezy (handles global VAT/tax compliance out of the box).
- **Quota Metric**: User-facing "Processed Lecture Minutes/Hours per month" + internal Gemini token cost tracking.

---

## Detailed Roadmap Phases

### Phase 0 — Architecture Preflight
| # | Item | Status | Rationale / Strategy |
|---|---|---|---|
| 0.1 | App Topology Decision | ✅ Decided | Keep unified Vite React 19 SPA (`frontend/`) for both landing & workspace app. Share auth via Supabase JWT. |
| 0.2 | Rebuild Roadmap Audit | ✅ Verified | Aligned with `context.md` §2 roadmap. SQLite -> Postgres modernization un-deferred. |
| 0.3 | Gemini Paid Tier Preflight | ⚠️ Launch Blocker | Must upgrade Google AI Studio from Free Tier (15 RPM / 500 RPD) to Pay-as-you-go Tier 1 before public launch. |

---

### Phase 1 — Landing Page & Marketing Site (Architect's Sketchbook Theme)
| # | Item | Status | Rationale |
|---|---|---|---|
| 1.1 | Hero VCP | ✅ Completed | *"Turn Any Lecture Video Into High-Grade Study Notes & AI Tutor"* in `font-serif` Newsreader + red-pencil emphasis. |
| 1.2 | Interactive Workspace Mockup | ✅ Completed | Built live preview card with tabbed switching (Study Notes with KaTeX, RAG Tutor, Assessments, Concept Mind Map). |
| 1.3 | How-It-Works | ✅ Completed | Numbered 4-step blueprint sequence (01 Media Ingest -> 02 18-Stage Pipeline -> 03 Artifact Synthesis -> 04 Socratic Tutor). |
| 1.4 | Feature Highlights | ✅ Completed | Grid showcasing Chapter Notes, Revision Cheat-Sheets, Grounded Tutor, Concept Mind Maps, and Quiz History. |
| 1.5 | FAQ & CTA | ✅ Completed | Primary CTAs *"Start Free Trial"* and *"Try 1 Video Free"* + trust badges. |
| 1.6 | Styling System | ✅ Completed | Full **Architect's Sketchbook** design token integration (`bg-nb` drafting vellum, `bg-ns`, `text-nt`, `text-np` red-pencil, `shadow-bp` offset blueprint shadows). |

---

### Phase 2 — Auth System (Supabase Auth)
| # | Item | Status | Rationale |
|---|---|---|---|
| 2.1 | Authentication Methods | ✅ Completed | Email/Password + Google OAuth + 1-video Free Trial Guest mode built in `AuthModal.tsx`. |
| 2.2 | Frontend Session Sync | ✅ Completed | Zustand store (`useAuthStore.ts`) managing JWT session persistence & profile metadata. |
| 2.3 | FastAPI Backend Security | ✅ Completed | Implemented `decode_supabase_jwt` and `get_current_user_optional` in `backend/auth.py`. |

---

### Phase 3 — Database Migration (SQLite → Supabase Postgres)
| # | Item | Status | Rationale |
|---|---|---|---|
| 3.1 | Relational Schema | ✅ Completed | Defined models: `User`, `Subscription`, `Lecture`, `UsageLog`, `WebhookEvent` in `backend/db/models.py`. |
| 3.2 | ORM Layer | ✅ Completed | Async SQLAlchemy 2.0 (`asyncpg` / `aiosqlite` fallback) in `backend/db/database.py`. |
| 3.3 | LangGraph Threads | ✅ Completed | Centralized DB tables prepared for thread history & checkpoints. |
| 3.4 | Disk Artifact Layout | ✅ Preserved | Artifacts on disk (`outputs/<lecture_id>/`) remain canonical for screenshots, audio, and Chroma DB vector stores. |

---

### Phase 4 — Free Trial Strategy
| # | Item | Status | Rationale |
|---|---|---|---|
| 4.1 | Server-Side Pre-Check | ✅ Completed | Pre-pipeline video duration probe in `orchestrator.py` validating media length. |
| 4.2 | Free Trial Ceiling | ✅ Completed | 1 Video (≤15 minutes max duration). Full access to all generated artifacts for that 1 video. |
| 4.3 | Conversion Gate | ✅ Completed | Hard paywall & quota check raising `HTTP 429` when free trial or monthly minutes quota is exceeded. |

---

### Phase 5 — Payment System (Lemon Squeezy)
| # | Item | Status | Rationale |
|---|---|---|---|
| 5.1 | Merchant of Record | ✅ Completed | Integrated Lemon Squeezy (handles global VAT, GST, tax remittance). |
| 5.2 | Webhook Handling | ✅ Completed | POST `/api/webhooks/lemonsqueezy` handler in `backend/routers/webhooks.py` with HMAC SHA256 signature verification & `WebhookEvent` idempotency table. |
| 5.3 | Events Managed | ✅ Completed | Sync `subscription_created`, `subscription_updated`, and `subscription_cancelled` to `subscriptions` table. |

---

### Phase 6 — Pricing Tiers & Quotas
| Tier | Price | Included Quota | Key Features |
|---|---|---|---|
| **Free Trial** | $0 | 1 video (≤15 mins) | Full features on 1 lecture |
| **Starter** | $9 - $11 / mo | 5 Lecture-Hours / mo (~15-20 lectures) | Full Pipeline, Flashcards, Quiz, Tutor |
| **Pro Student** | $23 - $29 / mo | 25 Lecture-Hours / mo (~80-100 lectures) | Priority processing, extended tutor history |

| # | Item | Status | Rationale |
|---|---|---|---|
| 6.1 | Quota Enforcement | ✅ Completed | `GET /quota` API and pre-check in `POST /process` rejecting requests with HTTP 429 when monthly limit is reached. |
| 6.2 | Quota Indicator Badge | ✅ Completed | Built Sidebar Quota Badge in `Sidebar.tsx` displaying remaining free trial / plan minutes. |
| 6.3 | Pricing Page UI | ✅ Completed | Built `PricingPage.tsx` with interactive Monthly/Annual billing toggle (save 20%) & Sketchbook blueprint cards. |

---

## Open Questions & Decisions Summary (Q1–Q6)

- **Q1 — App Topology**: Single unified Vite React 19 SPA (`frontend/`).
- **Q2 — Target Audience**: Students & University Course Capture ("Turn any lecture into study notes in seconds").
- **Q3 — Free Trial Conversion**: Full output access on 1 video (≤15 min) -> Paywall on video #2.
- **Q4 — Quota Metric**: User-facing "Lecture Minutes / Hours" + internal Gemini token cost logging.
- **Q5 — DB Cutover**: Clean-slate Postgres schema (no migration needed for gitignored `outputs/` dev data).
- **Q6 — Tutor Threads Schema**: Centralized Postgres tables (`user_threads`, `tutor_messages`) using LangGraph `AsyncPostgresSaver`.

---

## Implementation Dependencies & Sequencing (Gantt)

```
Phase 0 (Preflight & Paid Gemini API)
   │
   ▼
Phase 3 (Postgres Database Migration) ──┐
   │                                   │
   ▼                                   ▼
Phase 2 (Supabase Auth)         Phase 5 (Lemon Squeezy Payments)
   │                                   │
   ▼                                   ▼
Phase 4 (Free Trial Enforcement)  Phase 6 (Pricing Tiers & Quota Checking)
   │                                   │
   └─────────────────┬─────────────────┘
                     │
                     ▼
             Launch & Testing (✅ All Code Implemented)
```
