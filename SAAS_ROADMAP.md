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

### Phase 1 — Landing Page & Marketing Site
| # | Item | Status | Rationale |
|---|---|---|---|
| 1.1 | Hero VCP | ⏳ Planned | *"Turn any lecture video into study notes, revision cheat-sheets, flashcards, and an AI tutor in seconds."* |
| 1.2 | Social Proof | ⏳ Planned | Pre-launch slot: *"50 videos processed during private beta"*. |
| 1.3 | How-It-Works | ⏳ Planned | Numbered 4-step sequence: Upload (YT/GDrive/file) -> Transcribe & Extract -> Study Artifacts -> AI Tutor. |
| 1.4 | Feature Highlights | ⏳ Planned | Showcase Chapter Notes, Revision Cheat-Sheet, Assessments, Flashcards, and Visual Chapter Screenshots. |
| 1.5 | FAQ & CTA | ⏳ Planned | 6-8 key FAQs (Privacy, formats, refund policy) + primary CTA *"Start Free Trial"*. |
| 1.6 | Core Web Vitals | ⏳ Planned | Fast LCP hero, font-display swap, modern typography ("Architect's Sketchbook" theme). |

---

### Phase 2 — Auth System (Supabase Auth)
| # | Item | Status | Rationale |
|---|---|---|---|
| 2.1 | Authentication Methods | ⏳ Planned | Email/Password + Google OAuth natively managed via Supabase Auth. Support anonymous -> registered upgrade path. |
| 2.2 | Frontend Session Sync | ⏳ Planned | Vite SPA verifies Supabase JWT and attaches `Authorization: Bearer <jwt>` to all FastAPI calls. |
| 2.3 | FastAPI Backend Security | ⏳ Planned | Implement PyJWT / `fastapi-security` middleware in `backend/auth.py` to validate tokens on `/process`, `/lectures`, and `/tutor`. |

---

### Phase 3 — Database Migration (SQLite → Supabase Postgres)
| # | Item | Status | Rationale |
|---|---|---|---|
| 3.1 | Relational Schema | ⏳ Planned | Create tables: `users`, `subscriptions`, `lectures`, `chapters`, `user_threads`, `tutor_messages`, `webhook_events`. |
| 3.2 | ORM Layer | ⏳ Planned | Async SQLAlchemy 2.0 (`asyncpg`) replacing raw `sqlite3` and `outputs/lectures.json`. |
| 3.3 | LangGraph Threads | ⏳ Planned | Swap per-lecture SQLite `SqliteSaver` to central Postgres checkpoints via LangGraph `AsyncPostgresSaver`. |
| 3.4 | Disk Artifact Layout | ⏳ Preserved | Artifacts on disk (`outputs/<lecture_id>/`) remain canonical for screenshots, audio, and Chroma DB vector stores. |

---

### Phase 4 — Free Trial Strategy
| # | Item | Status | Rationale |
|---|---|---|---|
| 4.1 | Server-Side Pre-Check | ⏳ Planned | Duration probe via `ffmpeg.probe` / YouTube info before pipeline starts (`ingest/ingest.py`). |
| 4.2 | Free Trial Ceiling | ⏳ Planned | 1 Video (≤15 minutes max duration). Full access to all generated artifacts for that 1 video. |
| 4.3 | Conversion Gate | ⏳ Planned | Hard paywall modal triggered when attempting to upload video #2. |

---

### Phase 5 — Payment System (Lemon Squeezy)
| # | Item | Status | Rationale |
|---|---|---|---|
| 5.1 | Merchant of Record | ⏳ Planned | Lemon Squeezy (handles global VAT, GST, tax remittance). |
| 5.2 | Webhook Handling | ⏳ Planned | POST `/api/webhooks/lemonsqueezy` handler in FastAPI with signature verification & `WebhookEvent` idempotency table. |
| 5.3 | Events Managed | ⏳ Planned | Sync `subscription_created`, `subscription_updated`, `subscription_cancelled`, and `payment_failed` to `subscriptions` table. |

---

### Phase 6 — Pricing Tiers & Quotas
| Tier | Price | Included Quota | Key Features |
|---|---|---|---|
| **Free Trial** | $0 | 1 video (≤15 mins) | Full features on 1 lecture |
| **Starter** | $9 - $12 / mo | 5 Lecture-Hours / mo (~15-20 lectures) | Full Pipeline, Flashcards, Quiz, Tutor |
| **Pro** | $24 - $29 / mo | 25 Lecture-Hours / mo (~80-100 lectures) | Priority processing, extended tutor history |

| # | Item | Status | Rationale |
|---|---|---|---|
| 6.1 | Quota Enforcement | ⏳ Planned | Server-side check in `orchestrator.run_pipeline()` checking user's monthly remaining minutes before launching LLM calls. |
| 6.2 | Usage Metering | ⏳ Planned | Log processed minutes and actual Gemini API token costs per lecture in `UsageLog` for margin tracking. |

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
             Launch & Testing
```
