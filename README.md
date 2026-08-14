# 🧠 NorAI

### From lecture video to an interactive learning workspace.
**NorAI is an end-to-end multimodal AI platform that transforms
long-form lectures into structured study notes, revision material,
assessments, flashcards, important visual references, and a
lecture-grounded AI tutor.**

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-Frontend-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-Frontend-3178C6?style=for-the-badge&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Gemini](https://img.shields.io/badge/Gemini-Multimodal_AI-8E75B2?style=for-the-badge&logo=googlegemini&logoColor=white)](https://ai.google.dev/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agent_Workflows-1C3C3C?style=for-the-badge)](https://www.langchain.com/langgraph)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-Vector_Store-FF6B35?style=for-the-badge)](https://www.trychroma.com/)
[![Supabase](https://img.shields.io/badge/Supabase-Auth_+_Postgres-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)](https://supabase.com/)

**Lecture In → Understanding → Structure → Practice → Recall → Conversation**

## ✨ What is NorAI?

Watching a lecture is easy. **Revising it effectively is not.**

A technical lecture can contain definitions hidden in speech, code shown
only on screen, diagrams absent from the transcript, examples scattered
across timestamps, and concepts that only make sense when audio and
visuals are considered together.

Most lecture tools reduce that complexity to:

```
Video → Transcript → Summary
```

NorAI takes a different approach:

```
Lecture Video
     ↓
Speech + Visual Understanding
Structured Knowledge
Dynamic Chapters
Notes + Revision + Assessment + Flashcards
Lecture-Grounded AI Tutor
```

> **NorAI does not just summarize a lecture. It reconstructs it into a
> structured, interactive learning system.**

## 🌟 What NorAI Does

| Feature | What it does |
|---|---|
| 📝 **Study Notes** | Detailed, chapter-aware notes generated from structured lecture knowledge |
| ⚡ **Revision Notes** | High-density summaries designed for rapid review |
| 🧪 **Assessments** | Chapter-specific MCQ, True/False, short-answer, and scenario-style questions |
| 🃏 **Flashcards** | Recall cards with concise answers, explanations, and confidence ratings |
| 🗓️ **Spaced Repetition** | SM-2 scheduling with due-date filtering + **Anki `.apkg` export** (P6.2) |
| 🎬 **Click-to-Video** | Chapter/section answers link to the exact YouTube moment (P6.3) |
| 📚 **Course Collections** | Group lectures into courses; share them via public links (P6.4) |
| 📊 **Usage Dashboard** | Per-stage Gemini usage & estimated cost breakdown (P6.5) |
| 🖼️ **Important Visuals** | Relevant lecture frames mapped back to concepts and note sections |
| 🤖 **AI Tutor** | Retrieval-grounded Q&A over lecture-specific notes and visual context |
| 💬 **Persistent Threads** | Lecture-scoped tutor conversations with saved history |
| ✨ **Highlight & Ask** | Select text in study material and ask the tutor directly |
| 🔍 **Document Search** | Search generated learning material inside the workspace |
| 📄 **PDF Export** | On-demand, print-ready study, revision, and assessment documents |
| 📚 **Multi-Lecture Workspace** | Isolated artifacts, state, retrieval indexes, and conversations per lecture |

## 🧠 Why NorAI is Different

### 1. Multimodal by design
Lectures are not audio files with decorative video. NorAI separately
processes spoken explanations, timestamped transcript segments, code
visible on screen, slides, diagrams, whiteboard content, interfaces,
demonstrations, and other educationally important frames.

### 2. Dynamic lecture structure
NorAI does **not** assume every lecture has a fixed number of chapters.
The outline stage determines lecture title, chapter count, boundaries,
titles, focus concepts, and source chunk membership.

### 3. Lecture-scoped retrieval
Every lecture gets isolated artifacts, a per-lecture Chroma index, and a
per-lecture tutor graph. Tutor answers are grounded in the active lecture
instead of a shared global knowledge pool — and citations are **verified**
before they are shown (a deterministic post-check drops fabricated ones).

### 4. Built for active learning
Understand → Revise → Test → Recall → Ask
Notes, revision, assessments, flashcards, and tutoring live in one
connected workspace.

## 🏗️ System Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                    React + TypeScript Frontend                     │
│                                                                    │
│  Lecture Sidebar  │  Notes / Revision / Assessment  │  AI Panel   │
│  Chapters         │  Search / Highlight & Ask        │  Tutor      │
│  Lectures         │  Important Visuals               │  Quiz       │
│  Threads          │  PDF Export                      │  Flashcards │
└──────────────────────────────┬─────────────────────────────────────┘
                               │ REST + Polling
┌──────────────────────────────▼─────────────────────────────────────┐
│                         FastAPI Backend                            │
│  Auth (Supabase JWT/JWKS)  │  APIs  │  Webhooks  │  Tutor / Quota  │
│                                                                   │
│                 DB-Backed Job Queue (backend/jobs.py)             │
│                 supervisor thread + bounded worker pool            │
│                 sync pipeline runs inside a worker thread          │
│  Ingest → Transcribe → Extract → Visual → Outline → Merge →       │
│  Chapters → Notes/Revision/Assessment/Flashcards → Index          │
└──────────────┬────────────────────────────┬────────────────────────┘
               │                            │
      ┌────────▼─────────┐        ┌─────────▼────────────────┐
      │ Supabase Postgres │        │ Retrieval / Tutor Layer │
      │ users, lectures,  │        │ LangGraph, ChromaDB     │
      │ subscriptions,    │        │ Hybrid BM25 + dense     │
      │ usage_logs,       │        │ Verified citations       │
      │ webhook_events,   │        │ Persistent threads       │
      │ courses,          │        │ Real token streaming     │
      │ share_links       │        │ (astream_events, P6.1)   │
      └───────────────────┘        └──────────────────────────┘
```

The pipeline itself is **fully synchronous** and runs inside a worker
thread owned by a **DB-backed job queue** (`backend/jobs.py`): `POST
/process` enqueues a `Lecture` row (`status="queued"`), a supervisor
thread claims it within global + per-user concurrency caps, and the job
survives restarts — a stale heartbeat re-queues the job and, because
every stage is cache-first, recovery is near-free. Progress is persisted
to the DB and **polled** by the frontend (no SSE).

## 🔄 18-Stage Processing Pipeline

| # | Stage | What happens |
|---|---|---|
| 1 | **Ingestion** | Resolve source (YouTube via `yt-dlp`, Drive via `gdown`, or upload) and create lecture-scoped media artifacts |
| 2 | **Transcription** | Faster-Whisper converts audio into timestamped transcript segments |
| 3 | **Chunking** | Adaptive chunking builds context-preserving transcript chunks |
| 4 | **Knowledge Extraction** | Per-chunk Gemini structured extraction: concepts, explanations, formulas, code, relationships |
| 5 | **Frame Extraction** | OpenCV samples the lecture's visual stream (runs in parallel with 2–4) |
| 6 | **Scene Detection** | Pixel-diff threshold dedup reduces frames to meaningful keyframes |
| 7 | **Chunk ↔ Screenshot Mapping** | Associates transcript chunks with relevant visuals by timestamp |
| 8 | **Dynamic Outline Generation** | LLM infers title, 3–6 chapters, boundaries, and focus concepts |
| 9 | **Visual Understanding** | Gemini multimodal reads chapter-batched keyframes → `visual_objects/` |
| 10 | **Knowledge Merging** | Fuses textual + visual knowledge into merged objects |
| 11 | **Chapter Building** | Aggregates merged objects into typed chapters (no LLM) |
| 12 | **Screenshot Selection** | Two-pass quality scoring → perceptual-hash dedup → top-K ranking |
| 13–16 | **Consolidated Chapter Artifacts** | **One Gemini call per chapter** produces study notes + revision + assessment + flashcards (`MergedChapterArtifactsModel`) — stages 13–16 are a single consolidated call |
| 17 | **Tutor Index** | Diff-syncs embeddings of `notes/chapter_*.md` into the per-lecture Chroma `norai_notes` collection (content-hashed ids) |
| 18 | **Screenshot Index** | Indexes screenshot captions into `screenshot_captions` (diff-sync) |
| — | **Cleanup** | Deletes transient dirs on success, failure, or cancel |

Because every expensive stage is **hash-of-inputs cached** (P1) and the
index is diff-synced, re-running a lecture costs ~0 Gemini calls.

## 🔬 Inside the Multimodal Pipeline

### 🎙️ Speech Understanding
NorAI uses **Faster-Whisper** and preserves timestamp-aware transcript
segments.

`Audio → Timestamped Transcript → Context-Preserving Chunks → Structured Knowledge`

### 📸 Visual Understanding
`Video → Frame Extraction → Scene Detection → Keyframes → Temporal Chunk Mapping → Multimodal Analysis`

Visual analysis can capture code snippets, diagrams, formulas, slides,
architecture drawings, UI demonstrations, and worked examples.

### 🧬 Knowledge Fusion

```
Spoken Knowledge ─────────┐
                          ├──► Unified Lecture Knowledge
Visual Knowledge ─────────┘
```

### 🧭 Dynamic Outline Generation
The lecture outline is generated from processed knowledge itself. A
lecture can become four chapters, six chapters, or another structure
depending on content.

## 🤖 Lecture-Grounded AI Tutor

```
User Question
      ↓
Lecture-Scoped Hybrid Retrieval (BM25 + dense, RRF-fused)
Relevant Note Chunks + Screenshot Context + Conversation State
      ↓
Grounded Tutor Response (verified citations)
```

The tutor layer includes:

- **LangGraph** for stateful AI workflows (with **async** nodes on an
  `AsyncSqliteSaver` checkpointer so turns don't block the event loop)
- **ChromaDB** for persistent vector retrieval, plus **BM25** for lexical
  search fused via **RRF** (reciprocal rank fusion)
- lecture-specific note indexes and screenshot-caption retrieval
- persistent conversation threads per lecture
- **real token streaming** — `/chat/stream` drives the graph with
  `graph.astream_events(version="v2")` and forwards `on_chat_model_stream`
  events from the answer node, so replies render as tokens are generated (P6.1)
- verified citations — only sources that pass a deterministic post-check
  are shown; low-confidence retrieval answers say so explicitly
- contextual tools, commands, and quiz-in-chat

### ✨ Highlight & Ask
`Study Notes → Select Text → Highlight & Ask → Tutor with selected context`

## 🖥️ Learning Workspace

### 📝 Study Notes
Chapter-aware content with card-based sections, callouts, tables,
syntax-highlighted code, mathematical notation, and selected lecture
visuals.

### ⚡ Revision Notes
Condensed material for exam revision, interview preparation, pre-class
review, and quick concept refresh.

### 🧪 Assessment
Generated Multiple Choice, True/False, Short Answer, and Scenario-Based
questions.

### 🃏 Flashcards
Cards contain a front, back, explanation, and `Again` / `Hard` / `Good`
/ `Easy` confidence ratings with review statistics. Since **P6.2** ratings
drive **SM-2 spaced repetition** (interval/ease progression with a Due
filter), and the whole deck can be exported as an **Anki `.apkg`** file.

### 🎬 Click-to-Video Grounding (P6.3)
Per-chapter YouTube seek maps (`backend/video_map.py`) are built during the
visual stage. The workspace docks the lecture player, auto-seeks when you
switch chapters, and "Watch video" buttons jump to the exact moment for a
note section or tutor citation.

### 📚 Courses & Sharing (P6.4)
Lectures can be grouped into **course collections** (`CoursesPage`). Any
lecture can be shared with a link minted from the DocPanel **ShareModal** —
the public share page exposes only sanitized content (title, PDF, sample
questions), never raw transcripts, answer keys, or the tutor
(**closed-by-default** access model).

### 📊 Usage & Cost Dashboard (P6.5)
`backend/usage_ledger.py` rolls up per-stage token/cost rows into `GET
/usage`, rendered by `UsagePage.tsx` — see exactly where Gemini spend goes.

## 📚 Multi-Lecture by Design

Workspace routes are lecture-specific: `/workspace/{lectureId}`.

Artifacts are isolated under `outputs/`:

```
outputs/
├── lectures.json
├── <lecture-id-a>/
│   ├── videos/ · audio/ · metadata/
│   ├── transcripts/ · chunks/ · objects/ · visual_objects/
│   ├── merged_objects/ · mappings/ · chapters/
│   ├── notes/ · revision/ · assessment/ · flashcards/
│   ├── screenshots/
│   └── tutor/  (chroma index + graph checkpoints)
└── <lecture-id-b>/
    └── ...
```

Lecture identity propagates through routes, Zustand stores, backend
requests, documents, assessments, flashcards, screenshots, tutor
indexes, conversation threads, and PDF generation.

## 📄 On-Demand PDF Generation

NorAI supports downloadable Study Notes, Revision Notes, Assessments,
guide PDFs, and concept maps — generated on demand via the browser print
pipeline (React renders a print page, CSS `@page` rules drive pagination,
`window.print()` produces the PDF). PDFs are generated when requested
rather than during every pipeline run.

## 🛠️ Tech Stack

| Layer | Technology | Role |
|---|---|---|
| **Frontend** | React 19, TypeScript | Interactive learning workspace |
| **Build Tooling** | Vite 8 | Frontend development and bundling |
| **Styling** | Tailwind CSS 4 | UI system (design tokens) |
| **State** | Zustand | Lecture, chapter, and workspace state |
| **Routing** | React Router | Lecture-aware navigation |
| **Documents** | React Markdown, KaTeX | Markdown and math rendering |
| **Backend** | FastAPI, Uvicorn | APIs, webhooks, quota, pipeline integration |
| **Job Queue** | DB-backed (SQLAlchemy) | Durable pipeline scheduling (P4) |
| **AI** | Google Gemini (`gemini-3.1-flash-lite`) | Text generation and multimodal understanding |
| **AI Workflows** | LangGraph | Stateful tutor flows |
| **Speech** | Faster-Whisper | Lecture transcription |
| **Vector Store** | ChromaDB + BM25 | Hybrid (RRF-fused) retrieval |
| **Visual Processing** | OpenCV | Frame and image processing |
| **Media** | FFmpeg | Audio/video processing |
| **Video Sources** | yt-dlp, gdown | Online video ingestion |
| **Auth + DB** | Supabase | JWT auth (JWKS), Postgres storage |
| **Schema** | Alembic | Versioned migrations (P4.3) |
| **Storage** | File system, Supabase Postgres, ChromaDB, SQLite | Artifacts, app data, vectors, checkpoints |

## 🗂️ Repository Structure

```
NorAI/
├── config.py                     # single source of truth (model, dirs, quota, API key)
├── cache_util.py                 # hash-of-inputs caching markers (P1.4)
├── backend/
│   ├── main.py                   # all routes (incl. /process, /chat, /quota, /billing)
│   ├── orchestrator.py           # sync 18-stage pipeline (runs in job worker thread)
│   ├── jobs.py                   # DB-backed job queue + supervisor (P4.1)
│   ├── auth.py                   # Supabase JWT/JWKS verification (fail-closed)
│   ├── usage.py                  # usage metering + quota rollover (P2)
│   ├── estimator.py              # self-calibrating cost/time estimator (P1.8)
│   ├── ratelimit.py              # RPM limiter for Gemini calls
│   ├── db/                       # async SQLAlchemy engine, models, migrations
│   ├── routers/                  # (webhooks router used; rest empty)
│   └── test_*.py                 # standalone offline test suites
├── ingest/  transcription/  chunking/
├── extract/  visual/  notes/
├── revision_notes/  assessment/  flashcards/
├── tutor/                        # RAG tutor: graph, nodes, retriever, bm25,
│                                 # embedding, memory, quiz_nodes, citations, llm
├── migrations/  +  alembic.ini   # versioned schema migrations (P4.3)
├── frontend/                     # React 19 + TS (src/, public/, vite.config.ts)
├── scripts/
│   ├── start-dev.sh              # idempotent dev servers (backend + frontend)
│   └── run-tests.sh              # runs all offline test_*.py suites
├── Dockerfile  +  docker-compose.yml   # single-container deploy (P5.4)
├── .github/workflows/ci.yml      # CI: offline tests + lint + build (P5.3)
├── outputs/                      # ALL generated artifacts (gitignored)
├── PROJECT_PROGRESS.md  ROADMAP.md  COMMUNICATOR.md
├── AGENTS.md  NOTES.md  audit/  docs/
├── DEPLOYMENT_PLAN.md            # agreed production deployment path (Hostinger VPS)
├── UI_UX_AUDIT_REPORT.md         # frontend audit → executed design fixes
└── requirements.txt
```

## 🚀 Getting Started

### Prerequisites
- Python 3.12+
- Node.js 20.19+ (Vite 8 requirement; install via nvm if needed)
- npm
- FFmpeg
- Git
- Google Gemini API key (`GEMINI_API_KEY`)
- A Supabase project (for auth + Postgres; optional to run the pipeline alone)

### 1. Clone
```bash
git clone <YOUR_REPOSITORY_URL>
cd NorAI
```

### 2. Create the Python environment
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Python dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment
```bash
cp .env.example .env   # then fill in:
# GEMINI_API_KEY=...
# SUPABASE_URL=...  VITE_SUPABASE_URL=...  VITE_SUPABASE_ANON_KEY=...
# DATABASE_URL=postgresql://...   (Supabase session pooler)
# LEMONSQUEEZY_WEBHOOK_SECRET=...
```
> Never commit secrets or API keys — `.env` is gitignored.

### 5. Install frontend dependencies
```bash
cd frontend && npm install && cd ..
```

### 6. Start the dev servers
```bash
scripts/start-dev.sh start     # both backend (:8000) + frontend (:5173), daemonized
scripts/start-dev.sh status    # check health; stop to shut down
```
or manually: `venv/bin/python -m uvicorn backend.main:app --reload --port 8000`
(backend, from repo root) and `cd frontend && npm run dev` (frontend).

API docs: http://localhost:8000/docs

### 7. Run the tests
```bash
scripts/run-tests.sh           # all offline backend test_*.py suites
cd frontend && npm run test    # Vitest frontend suites
npm run build                  # tsc -b + vite build (CI parity)
```

**Quotas:** Free trial = 1 video of ≤15 minutes. Starter = 300
minutes/month. Pro = 1500 minutes/month. Usage is metered per completed
lecture and enforced *before* any Gemini spend.

## 🧪 Development Status

NorAI is under **active development** — the SaaS foundation (auth,
billing, job durability), the retention feature set, and the token-reduction
sprint are complete; a production deployment path is agreed in
[`DEPLOYMENT_PLAN.md`](DEPLOYMENT_PLAN.md).

### Implemented
- [x] Lecture video ingestion (YouTube / Drive / upload)
- [x] Faster-Whisper transcription with timestamped segments
- [x] Adaptive chunking + structured knowledge extraction
- [x] Multimodal visual understanding (frames, scenes, mapping, analysis)
- [x] Dynamic outline generation + chapter construction
- [x] Study notes, revision notes, assessment, flashcards (one call/chapter)
- [x] Important screenshot selection + screenshot-caption retrieval
- [x] Multi-lecture artifact isolation + lecture registry
- [x] React + TypeScript workspace with progress polling
- [x] Lecture-specific ChromaDB indexes, hybrid retrieval, verified citations
- [x] Persistent tutor threads + Highlight & Ask + document search
- [x] On-demand PDF generation (notes, revision, assessment, guide, mind-map)
- [x] Supabase auth (JWKS verification) + Postgres persistence
- [x] Lemon Squeezy webhooks, usage metering, quota enforcement, billing page
- [x] DB-backed job queue with restart recovery (P4)
- [x] P0–P5 hardening: security, pipeline economics, retrieval evals, CI, Docker, tests
- [x] **P6 retention** — real token streaming (P6.1), SM-2 spaced repetition +
      Anki export (P6.2), click-to-video grounding (P6.3), course collections +
      share links (P6.4), usage/cost dashboard (P6.5)
- [x] **P7 token reduction** — prompt compression, context caching (dormant on
      free tier), output-token cuts (`docs/token_reduction.md`)
- [x] **UI/UX audit execution** — 3 responsive tiers, skeletons, custom Select,
      dark-theme fixes, course/share pages (`UI_UX_AUDIT_REPORT.md`)

## 🧩 Engineering Challenges

NorAI is also a practical exploration of real-world AI systems engineering:

- orchestrating long-running multi-stage AI pipelines without starving API progress endpoints
- making the pipeline durable: DB-backed job queue, heartbeat-stale recovery, retry-with-backoff
- persisting async LangGraph state (AsyncSqliteSaver) so chat turns don't block the event loop
- migrating schema with Alembic (`create_all` → versioned migrations, legacy DB absorption)
- verifying Supabase JWTs via JWKS across HS256 → ES256 key rotation
- securing and de-duplicating payment webhooks (HMAC, fail-closed, idempotency)
- enforcing quota before any LLM spend, and self-calibrating cost estimates from real metrics
- isolating artifacts and retrieval indexes per lecture, preventing cross-lecture state leaks
- handling malformed JSON from LLM responses and retrying structured generation
- mapping timestamped transcript chunks to visual keyframes and fusing text + visual knowledge
- dynamically determining chapter counts and boundaries
- cutting re-run cost to ~0 with hash-of-inputs caching + diff-synced vector indexing
- tuning print CSS for exactly-one-page-per-chapter PDFs and keeping screenshots in the print
- rendering Markdown, KaTeX math, code, and callouts consistently
- keeping a streaming chat responsive (React memo composition + real token streaming via `astream_events`, P6.1)
- implementing SM-2 spaced repetition + a from-scratch Anki `.apkg` exporter without third-party packages
- building share links with a **closed-by-default** access model (sanitized public views, no answer/transcript leaks)
- hardening the frontend: strict TypeScript, code-splitting, error boundaries, AbortController polling
- testing without a framework: standalone offline `test_*.py` suites + Vitest + offline API contract tests

## 🧭 Design Principles

1. **Ground everything in the lecture** — generated material stays connected to source content.
2. **Treat visuals as knowledge** — a lecture is not just a transcript.
3. **Keep lectures isolated** — artifacts, indexes, conversations, and frontend state follow lecture identity.
4. **Prefer dynamic structure** — different lectures need different chapter boundaries and counts.
5. **Design for partial failure** — one optional stage should not destroy all successful work.
6. **Build for learning, not summarization** — help learners understand, revise, test, recall, and ask.

## 🗺️ Roadmap

### Near Term
- [x] Authentication and user profiles (Supabase, JWKS)
- [x] Production-grade background job queue with resume/recovery
- [x] Structured-output hardening for LLM stages (typed models + retries)
- [x] Processing observability and cost analytics (structured logs, metering, estimator)
- [x] Verified tutor citations and source navigation
- [x] Dockerized single-container deployment + CI
- [x] Better mobile responsiveness (3 responsive tiers, UI/UX audit)
- [ ] Automated integration tests for full lecture runs (offline suites exist; live end-to-end pending)
- [ ] Cloud object storage

### Future
- [ ] Cross-lecture knowledge retrieval
- [x] Course-level organization *(shipped in P6.4)*
- [x] Spaced repetition scheduling *(shipped in P6.2)*
- [ ] Adaptive expertise tracking
- [ ] Personalized revision plans
- [ ] Weak-concept detection
- [ ] Learning analytics
- [ ] Knowledge graph visualization
- [ ] Collaborative study rooms
- [ ] Multilingual lecture workflows
- [ ] Adaptive assessments

## 📊 Performance & Cost

Pipeline runtime and model usage depend on lecture duration, transcript
chunk count, extracted keyframes, visual-analysis retries, model choice,
API rate limits, local hardware, and network conditions. `POST /estimate`
gives a per-lecture prediction of Gemini calls and wall-clock minutes,
self-calibrated from real recorded metrics (P1.8).

> Add reproducible benchmarks here with lecture duration, hardware,
> model, frame count, and pipeline configuration.

## 🤝 Contributing

Contributions, bug reports, experiments, and architecture discussions
are welcome.

```bash
git checkout -b feature/your-feature
git add .
git commit -m "Add your feature"
git push origin feature/your-feature
```

Then open a Pull Request. Especially valuable areas include retrieval
quality, multimodal evaluation, structured generation reliability,
frontend UX, accessibility, pipeline recovery, testing, observability,
and deployment.

## 🚀 Deployment

The agreed production path is documented in
**[`DEPLOYMENT_PLAN.md`](DEPLOYMENT_PLAN.md)**. Summary of decisions:

- **Host** — an existing **Hostinger KVM 1 VPS** (1 vCPU / 4 GB / 50 GB SSD).
- **Packaging** — **single-container** Docker image (Option B): FastAPI serves
  the built SPA, so there's no separate static host and **zero CORS** in prod.
- **TLS** — **Caddy** reverse proxy with automatic Let's Encrypt.
- **DNS** — **Cloudflare** (single `A` record to the VPS).
- **Data** — **Supabase Postgres** (free tier) + **Supabase Auth**; generated
  artifacts stay on the VPS under `outputs/` (volume-mounted).

## 🔐 Security Notes

Already applied:
- API keys live in environment variables; `.env` is never committed
- Webhook signature verification is **fail-closed** (unset secret → 503, mismatch → 401)
- Uploaded files are validated and size-limited; uploads are SSRF-gated (domain allowlist)
- JWT auth is fail-closed (ES256 via JWKS, HS256 fallback); anonymous-by-default for dev
- Global + per-user concurrency caps; quota enforced before any LLM spend
- Error sanitization: raw details go to logs, clients get generic responses
- Single-container image builds from pinned deps

Keep in mind for public deployment:
- add production rate limiting at the edge
- review generated content before high-stakes use
- tighten CORS beyond the dev allowlist

## 👨‍💻 Author

Built by **Gourav Kumar Singh**.

NorAI explores the intersection of:
- Artificial Intelligence
- Multimodal Learning
- Retrieval-Augmented Generation
- Full-Stack Engineering
- Educational Technology

## ⭐ If NorAI interests you, consider starring the repository.

**From passive watching to active learning.**

`Video → Understanding → Structure → Practice → Recall → Conversation`
