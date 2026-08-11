# NorAI — Engineering Roadmap

> Senior-engineer review of the full stack (backend, 18-stage pipeline, RAG tutor, frontend, infra), converted into an actionable, phased plan. Findings cite `file:line` — verify against source before starting an item.
>
> **Relationship to `SAAS_ROADMAP.md`**: that doc is the *launch track* (landing, auth, DB, trial, payments, pricing). This doc is the *engineering hardening track* — it covers the critical security/correctness gaps, pipeline economics, RAG quality, durability, and foundation work the launch track depends on. Several items marked ✅ there are actually non-functional (see Phase P0).

## Executive summary

NorAI has a working 18-stage multimodal pipeline, a genuinely grounded RAG tutor, and a polished React workspace. It is not production-ready. The blockers, in order:

1. **Security** — webhook signature check disabled by default (privilege escalation), entire `outputs/` served publicly (transcripts, answer keys, chat histories, vector DBs), SSRF + unbounded uploads, auth is advisory.
2. **Economics** — the pipeline costs 3–20× more than it should (chunk-size drift, unbatched embedding indexing, duplicate screenshot analysis, no caching on the most expensive stages).
3. **Monetization is non-functional** — `used_minutes_this_month` is never incremented, quota checks are bypassable, lecture status never updates.
4. **Durability** — pipeline jobs are fire-and-forget daemon threads with in-memory state; no cancellation, retry, resume, or migrations.
5. **Differentiation** — retrieval has no evals, no hybrid/rerank, no verified citations; streaming is fake; no retention features (spaced repetition, click-to-video).

## Sequencing overview

| Phase | Focus | Effort | Impact |
|---|---|---|---|
| **P0** | Security hardening | Small | Critical — blocks launch |
| **P1** | Pipeline economics | Small–Med | 3–20× cost/latency cut |
| **P2** | Billing & quota made real | Med | Business viability |
| **P3** | RAG quality + evals | Med | Product moat |
| **P4** | Job durability + migrations | Med–Large | Scales to real users |
| **P5** | Foundation (observability, CI, deploy, frontend) | Med–Large | Team velocity + reliability |
| **P6** | Retention features | Med | Differentiation & growth |

---

## Phase P0 — Security hardening (do first)

> **Status: COMPLETE.** All P0.1–P0.8 + P0.4a-server shipped and verified (curl probes + `backend/test_webhooks.py`, `test_auth_email.py`, `test_upload_validation.py`, `test_static_allowlist.py` — 48 assertions green). P0.4a-frontend deliberately **not** shipped — see the note below.

| # | Item | Status | Ref | Notes |
|---|---|---|---|---|
| P0.1 | Webhook fail-closed | ✅ | `backend/routers/webhooks.py:40-45` | Empty secret now rejects all events (503) unless `NORAI_ALLOW_UNSIGNED_WEBHOOKS=1` (dev only). Verified live: unsigned POST → 503. |
| P0.2 | Require explicit `user_id` in webhook custom_data | ✅ | `webhooks.py:106-110` | Missing `user_id` → event dropped (logged), never a silent no-op. Status normalized to `{trial,active,cancelled,past_due,paused}`; tier from exact `PLAN_TIER_BY_VARIANT` map (unknown → starter). Stable SHA-256 event-id fallback replaces `hash()`. |
| P0.3 | Stop serving `outputs/` publicly | ✅ | `backend/main.py` `resolve_static_path` | Blanket `StaticFiles` mount replaced with `/static/{path}` catch-all: resolves safely under `outputs/`, serves **image extensions only**. Verified: screenshots 200 via Vite proxy + browser; `checkpoints.sqlite`, `backend.log`, answer keys, Chroma, traversal → 404. |
| P0.4 | Enforce auth on data endpoints | ◐ | `backend/main.py` `ensure_lecture_access` | **P0.4a-server shipped:** 12 artifact-read endpoints (`/outline`, `/notes`, `/summary`, `/flashcards`, `/flashcards/ratings`, `/screenshots`, `/study-guide`, `/concept-map`, `/quiz/questions`, `/quiz/attempts`, `/missed`, `/lectures/{id}`) now 404 on foreign lectures **when a token is presented**; anonymous + `default` unchanged. **P0.4a-frontend intentionally NOT done:** the frontend sends no Bearer token on reads, so the check is dormant and nothing can regress. Wiring auth headers would 404 pre-auth/anonymous lectures for logged-in users (no attribution mechanism) — deferred until a lecture-claim/migration story exists (see P5.5 typed API client). |
| P0.5 | SSRF + upload hardening | ✅ | `backend/main.py` `/process` | `source_type` validated to `{youtube,gdrive,upload}`; youtube/gdrive URLs gated by `is_youtube_url`/`is_gdrive_url` (blocks `file://`, internal hosts) before any download; upload extension whitelist (415), chunked stream-write (no full-RAM buffer) with `NORAI_MAX_UPLOAD_BYTES` hard cap (413), upload file deleted after pipeline finishes. Verified: 400/413/415/cleanup all live. |
| P0.6 | Stop leaking exception detail | ✅ | `backend/main.py` + global handler | Chat/chat-stream return safe messages (detail → `logger.exception`); `/quiz/evaluate` parse failure returns 200 with a safe `overall_insights` (raw LLM text suppressed to log); global `@app.exception_handler(Exception)` returns generic 500 + logs. 404s unaffected. |
| P0.7 | Fix duplicate-email user creation | ✅ | `backend/auth.py` | On `IntegrityError` for `User.email unique`: rollback → re-fetch by id/email → resolve, never silently demote to anonymous. Missing Subscription rows are backfilled. |
| P0.8 | Remove `@anonymous.norai` forgeable heuristic | ✅ | `backend/auth.py:89-91` | `is_anonymous` comes from the Supabase `is_anonymous` JWT claim only (`signInAnonymously` sets it). Forged email suffixes no longer grant anonymous status. Guest flow verified in code path (`AuthModal.tsx:70`). |

---

## Phase P1 — Pipeline economics (3–20× cost cut)

| # | Item | Status | Ref | Notes |
|---|---|---|---|---|
| P1.1 | Chunk-size drift: use `config.py` value | ✅ | `chunking/chunk.py:15` (5) vs `config.py:28` (15) | Extraction is ~1 LLM call/chunk (`extract/extractor.py:82-126`). At 5 segments/chunk a 22-min lecture ≈ 119 chunks → ~10 min at the 12-RPM global limit; 3-hr lectures ≈ 2,000+ calls → hours. **Single highest-leverage fix.** `chunking/chunk.py` now imports `DEFAULT_SEGMENTS_PER_CHUNK`; covered by `chunking/test_chunk_defaults.py`. |
| P1.2 | Batched, cached embedding indexing | ✅ | `backend/orchestrator.py:298-308,343-351` | Upserts one doc/call (~1 embed call/chunk) vs `tutor/build_index.py:92-116` (batch 20 + rate-limit pacing). `tutor/build_index.py` now exposes `upsert_batched()` (batch 20 + `EMBED_BATCH_SLEEP_SEC` pacing); orchestrator Stage 17/18 delegate to it and diff-sync against the per-lecture `tutor/chroma` (content-hashed ids → no-op on identical re-runs, orphans deleted). Covered by `tutor/test_build_index_batching.py`. |
| P1.3 | Merge duplicate screenshot analysis | ✅ | `visual/visual_extractor.py:663-684`, `notes/screenshot_selector.py:514-661,1124-1273` | Same keyframes re-uploaded + re-scored by two stages (~34 multimodal calls for a 22-min lecture). `visual_extractor` persists `visual_analysis_ch{id}.json` per chapter; `screenshot_selector` loads it and synthesizes Pass 1 `FrameQualityScore`s (no re-upload/re-score) for analyzed frames. Covered by `notes/test_selector_cache.py`. |
| P1.4 | Caching on the 3 most expensive stages | ✅ | `extract/extractor.py`, `notes/screenshot_selector.py`, `notes/notes_generator.py:820-951` | No skip-if-exists → every re-run re-bills. New `cache_util.py` (hash-of-inputs → `.sha256` marker sidecar); wired into extraction (whole-stage + per-chunk), per-chapter note artifacts, per-chapter screenshot selection, plus whole-stage markers for visual extraction (`.visual_extract.sha256`) and outline (`.outline.sha256`). Orchestrator Stage-19 cleanup now **preserves** `objects/`/`visual_objects/`/`merged_objects/` (they previously deleted the caches every run). Covered by `test_cache_util.py`, `visual/test_visual_cache.py`, `notes/test_outline_cache.py`. |
| P1.5 | Delete dead / duplicated pipeline code | ✅ | `extract/__init__.py` (dup w/ `gemini-2.5-flash-lite`), `notes/chapter_structurer.py`, `notes/chapter_clusterer.py`, `revision_notes/revision_generator.py`, `assessment/assessment_generator.py`, `retrieval/`, `vectordb/`, `flashcards/generate_flashcards.py` langchain scaffolding | Imported-but-never-called (`orchestrator.py:31-34`), drift hazards. Deleted dead modules (`retrieval/`, `vectordb/`, chapter_structurer/clusterer, revision parser/models/prompts/pdf_builder, assessment generators/pdf_builder/renderer); `revision_generator` trimmed to `render_revision_markdown`; `extract/__init__.py` re-exports from `extractor`; flashcard langchain scaffolding removed; `from random import random` shadow bug fixed (`notes_generator.py:21,462`). |
| P1.6 | Fix `config.py` constants not honored | ✅ | `config.py:29-30`, `backend/ratelimit.py:29`, per-module retry counts | `DEFAULT_MAX_RETRIES`/`DEFAULT_RPM_LIMIT` are dead; retry counts (3 or 8) and limiter instances (`notes/outline_generator.py:14`) are re-hardcoded per module. `ratelimit.py`, `extract/extractor.py`, `notes_generator.py`, `screenshot_selector.py`, `visual_extractor.py` now honor config values; `outline_generator.py` uses the shared limiter. |
| P1.7 | Transcription upgrade | ✅ | `transcription/transcribe.py:20-23` | faster-whisper `base` (74M, CPU) is the accuracy ceiling for every downstream stage. Default moved to `small`, driven by `NORAI_WHISPER_MODEL` (env), with a per-size `_MODEL_CACHE` so consecutive lectures skip reload. Covered by `transcription/test_transcribe_config.py`. |
| P1.8 | Adaptive chunking + pre-flight cost estimate | ✅ | `chunking/chunk.py:43-66`, `backend/estimator.py` [NEW], `backend/main.py:/estimate`, `ingest/ingest.py:probe_video_metadata`, `backend/orchestrator.py` (metrics), `frontend/src/pages/UploadPage.tsx` | Long lectures grew to ~126 chunks at spc=15 (3-hr → ~126 extraction calls). `adaptive_segments_per_chunk()` bounds chunks to `TARGET_MAX_CHUNKS` (24) via `MAX_SEGMENTS_PER_CHUNK` (60) — 3-hr lecture ≈ 32 chunks (est. 57 total calls vs ~130+). New `POST /estimate` probes duration cheaply (yt-dlp `download=False`, ~2s) and returns ~calls/~minutes + free-trial fit; uploads use browser-read duration; Drive fails soft. **Self-calibration loop**: `orchestrator.py` snapshots LLM/embed counters + stage timings and appends actuals to `outputs/pipeline_metrics.jsonl`; `load_calibration()` re-fits segs-per-min, transcription realtime, sec/call, embed-batch time and the Pass-2 selection ratio from ≥5 fresh runs, tightening the estimate with every real run. `python -m backend.estimator --recalibrate` prints fitted constants + prediction error. Covered by `chunking/test_adaptive_chunking.py`, `backend/test_estimate.py` (34 checks). |

> **🚀 P1.8 — Self-calibrating pre-flight estimates (highlight):** every real pipeline run now
> appends its actuals to `outputs/pipeline_metrics.jsonl` (calls, embed batches, stage timings,
> planned-vs-actual). The estimator + adaptive-chunk constants re-fit from the recent fresh runs
> (≥5) each time `/estimate` is called, so the pre-flight cost/time figure and the chunk-size
> decision get measurably more accurate the more lectures you process — `python -m backend.estimator
> --recalibrate` shows the fitted constants and prediction error at a glance. DoD: 17 first-run / 0
> re-run calls confirmed, estimate baseline = 17 predicted vs 17 observed.

---

## Phase P2 — Make billing & quota real

| # | Item | Status | Ref | Notes |
|---|---|---|---|---|
| P2.1 | Increment usage metering | ✅ | `usage.py`, `orchestrator.py:488-518` | `record_pipeline_outcome` meters success minutes into `Subscription.used_minutes_this_month` + writes `UsageLog`; `Lecture.duration_seconds` set from probe. |
| P2.2 | Enforce quota before download | ✅ | `main.py:1218-1253` | `GET /quota` + `/process` gate: anonymous & free users share the 15-min free trial; 429 before any Gemini/download spend; duration-aware `used + needed > quota` check. |
| P2.3 | Persist lecture DB status | ✅ | `main.py:1297`, `orchestrator.py:491-518` | `Lecture.status` set to `completed`/`failed` + `duration_seconds` via `record_pipeline_outcome`. |
| P2.4 | Live quota badge + `/quota` call | ✅ | `Sidebar.tsx:55-57,231-266`, `useAuthStore.ts:67-108` | Badge reads live `/quota`; sends Bearer token via `authHeaders()`. Note: `refreshQuota` only emits a new `user` object when subscription fields change (prevents effect refetch loop). |
| P2.5 | Billing page + subscription state UI | ✅ | `frontend/src/pages/BillingPage.tsx`, `main.py:1105-1144` | `/billing` returns plan/usage/status + Lemon Squeezy `checkout_urls`/`manage_url`; page renders tier, usage bar, plan actions, manage link. Vite proxies `/billing` with an HTML bypass so the SPA route and API share the path. |

---

## Phase P3 — RAG quality & evals (the moat)

| # | Item | Status | Ref | Notes |
|---|---|---|---|---|
| P3.1 | Golden-QA eval suite | ✅ | `tutor/evals/` | Per-lecture golden sets (`golden_sets.py`), MRR/hit-rate runner (`runner.py`), calibration + regression tests (`test_evals.py`). |
| P3.2 | Hybrid search + reranking | ✅ | `tutor/bm25.py`, `retriever.py` | Rank-BM25 lexical index + cosine dense, RRF fusion, `chunk_id`/`relevant` returned; `test_hybrid.py`. (Adaptive top-k not yet done.) |
| P3.3 | Verified citations | ✅ | `tutor/citations.py`, `nodes.py:verify_citations_node`, `graph.py`, `backend/main.py`, `frontend` | Deterministic post-check of cited section names against retrieved chunk IDs; unverified citations never render (`test_citations.py`). |
| P3.4 | Chunk context expansion | ✅ | `tutor/context_expand.py` | Pulls parent-section + siblings around leaf hits (`test_context_expand.py`). |
| P3.5 | Cross-turn chapter state | ✅ | `tutor/nodes_retrieval.py`, `state.py` | `last_chapter_id` persisted; anaphoric follow-ups re-scope retrieval (`test_chapter_tracking.py`). |
| P3.6 | Fix memory degradation | ✅ | `tutor/nodes.py` | Summarised turns now removed via `RemoveMessage` (bounded store) + char-budget prompt window (`test_memory_nodes.py`). |
| P3.7 | Graceful low-context handling | ✅ | `nodes_retrieval.py`, `nodes.py`, `prompts.py` | `retrieval_status` ("ok"/"empty"/"error") + per-chunk `confidence_tag` ("strong"/"weak") + `_RETRIEVAL_ERROR_NOTE` (`test_low_confidence.py`). |

---

## Phase P4 — Job durability & data layer

| # | Item | Status | Ref | Notes |
|---|---|---|---|---|
| P4.1 | Real job queue | ✅ | `backend/jobs.py` (supervisor, worker pool), `main.py:1299-1311,1569-1600` | DB-backed queue (`queued→processing→completed/cancelled/failed`), supervisor claims within global + per-user caps, heartbeat-stale recovery with retry (≤3) + resume (cache-first ≈ 0 calls), `on_progress`/`should_cancel` callbacks, `PipelineCancelled`; `/process` enqueues, `/status` DB-backed, new `/cancel`. Single-process assumption noted. |
| P4.2 | Cleanup on failure | ✅ | `jobs.py:gc_sweep`, `orchestrator.py` (transient-dir removal on every outcome) | Worker deletes the upload post-run; boot + daily GC purges stale uploads (`UPLOAD_GC_AGE_HOURS`) and DB-orphaned lecture dirs (`ORPHAN_DIR_GC_AGE_DAYS`). |
| P4.3 | Migrations (Alembic) | ✅ | `backend/db/migrate.py`, `alembic.ini`, `migrations/versions/0001_initial`, `0002_lecture_pipeline_job_columns` | `run_migrations` on startup (idempotent); legacy `create_all` DBs absorbed + backfilled; `test_migrations.py` (13 checks) green. |
| P4.4 | Async tutor persistence | ✅ | `tutor/memory.py:58` (`get_async_checkpointer`), `backend/dependencies.py:82,161` (`_aget_or_create_lecture_graph`, `ainvoke_tutor`) | Tutor turns no longer block the event loop: chat nodes are `async` (`tutor/nodes.py`, `nodes_retrieval.py`, `quiz_nodes.py`) on `AsyncSqliteSaver` (WAL + busy_timeout), per-lecture `asyncio.Lock`, LRU graph cache bounded at `TUTOR_MAX_CACHED_GRAPHS` (32; conns closed on eviction); `/chat`, `/chat/stream`, `/threads/{id}` all `await`. Verified offline by `tutor/test_async_persistence.py` (3 checks). |
| P4.5 | Progress transport (SSE vs polling) | ✅ | `orchestrator.py:1-13`, `frontend/src/pages/ProcessingPage.tsx` | Decision: drop the dead SSE scaffolding, keep polling + harden the poller. `_queues`/`run_coroutine_threadsafe` scaffolding removed; progress flows via DB-backed `/process/{id}/status`. Poller hardened: AbortController on unmount, exponential backoff 1.5s→10s (reset on success), 404 → terminal error, `finished` dropped from effect deps (extra-request bug). oxlint + `tsc -b` green. |

---

## Phase P5 — Foundation

| # | Item | Status | Ref | Notes |
|---|---|---|---|---|
| P5.1 | Observability | ✅ | `backend/logging_config.py` [NEW], `backend/main.py` (request-id middleware), `tutor/llm.py` [NEW], `backend/jobs.py` | Structured JSON logs (console + rotating `outputs/backend.log`) via a shared `setup_logging()`; per-request `request_id` (X-Request-ID accept/echo) + job-runner context (`lecture_id`) via contextvars; `make_chat_llm` factory (`tutor/llm.py`) records per-call Gemini token usage to `outputs/llm_calls.jsonl` (thread-safe, silent-fail). All tutor nodes + `/quiz/evaluate` route through it. Covered by `tutor/test_async_persistence.py` + `tutor/test_memory_nodes.py` (offline). |
| P5.2 | Dependency hygiene | ✅ | `requirements.txt`, `requirements-dev.txt`, `.env.example` | Pinned exact versions (no `>=`), runtime list trimmed to what's imported (drops `langchain`/`streamlit`/`reportlab`/whisper/OCR cruft; adds `google-genai==2.8.0`, `faster-whisper`, `asyncpg`, `pyjwt`). `.env.example` committed with `!.env.example` gitignore exception. |
| P5.3 | CI | ✅ | `.github/workflows/ci.yml`, `scripts/run-tests.sh` | GH Actions: backend job (`pip install` + `scripts/run-tests.sh` runs every offline `test_*.py`, excludes `*_probe.py`); frontend job (`npm ci` + oxlint + `tsc -b`/`vite build` + `npm run test`). |
| P5.4 | Docker + deploy config | ✅ | `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `frontend/.npmrc` [NEW], `requirements.txt` (6 new pins) | Single-container image (multi-stage: React build → python run, SPA served by FastAPI) **built + smoke-verified** on Docker Desktop 4.83 WSL2. Build fixes that surfaced: `frontend/.npmrc` (`legacy-peer-deps=true` — openapi-typescript 7 peer-requires TS ^5 but repo pins ~6; the lockfile only ever installed under legacy peers, now reproducible for host+container; `Dockerfile` frontend stage copies `.npmrc`); `requirements.txt` gained `gdown`, `imagehash`, `numpy`, `pillow`, `langgraph`, `langgraph-checkpoint-sqlite` (all direct imports present only transitively/ad-hoc in the venv — `gdown` and `langgraph.checkpoint.sqlite` were boot-time `ModuleNotFoundError`s). Verified: boots, `/docs`+`/openapi.json` 200, SPA served for `/`, `/app`, `/workspace/...`, `/print?...` (Accept: text/html), API JSON routes unaffected; `docker compose config` valid, named `norai_outputs` volume + `.env` via `env_file`. Deploy doc: single-container, `CMD uvicorn backend.main:app --host 0.0.0.0 --port 8000`, `NORAI_SPA_DIST=/app/frontend/dist`. |
| P5.5 | Frontend: typed API client | ✅ | `src/lib/http.ts` [NEW], `frontend/src/types/api.ts` (openapi-typescript output), `tsconfig.app.json` (`strict: true`) | New shared `lib/http.ts`: `apiGet`/`apiPost`/`apiDelete`/`apiFetch`/`apiFetchRaw` merge auth headers + pass AbortSignal through, normalize errors into `ApiError` (with `detail` extraction), share one `API_BASE` (chatApi + useQuizStore constants consolidated). Return types derive from the generated `paths` schema when the explicit generic is omitted (`ApiJson<P,M>`), so re-running codegen tightens callers automatically. Every `any` removed from `frontend/src` (print pipeline typed via `PrintChapterPayload`, catch blocks narrowed to `unknown`, quiz normalization typed). `strict: true` enabled — full `tsc -b` clean. |
| P5.6 | Frontend: bundle & resilience | ✅ | `App.tsx` (React.lazy + Suspense), `src/components/ui/Markdown.tsx` [NEW], `src/components/AppErrorBoundary.tsx` [NEW], chat components (`MessageBubble`/`ReferencesPanel`/`ShimmerLoader`) | Entry chunk **1,353.71 kB → 363.78 kB** (400.85 → 117.16 kB gzip). All 7 pages are lazy route chunks (Landing 19 / Pricing 6 / Upload 12 / Processing 5 / Billing 8 / Print 12 / Workspace 96 kB); KaTeX+highlight+react-markdown live only in the shared workspace chunk via the new single `Markdown` renderer (was global `@import` — marketing pages no longer download KaTeX fonts). App-level `AppErrorBoundary` (was print-only); `MessageBubble`/`ReferencesPanel`/`ShimmerLoader` memoized so stream-token re-renders skip re-parsing completed bubbles. `strict: true` clean; oxlint green; browser smoke: landing loads no markdown stack, workspace Notes/Revision render, print route renders all chapters. |
| P5.7 | Frontend: polling → SSE | ✅ | `ProcessingPage.tsx:83-104` | Real SSE dropped by decision (P4.5) — polling kept. Poller hardening landed in P4.5: AbortController, exponential backoff 1.5s→10s, 404 → terminal error, `finished` removed from effect deps. |
| P5.8 | Frontend tests + API contract tests | ⬜ | no `*.test.*`, `backend/test_api_contract.py` is a live-server probe | Vitest/RTL for components; move contract tests to a framework; add `/process`, `/chat`, and auth negative cases. |

---

## Phase P6 — Retention & differentiation features

| # | Item | Status | Ref | Notes |
|---|---|---|---|---|
| P6.1 | Real token streaming | ⬜ | `backend/main.py:275-286` | `/chat/stream` computes the full answer then re-chunks it in fake 24-char frames. Use LangGraph `astream_events`. |
| P6.2 | Spaced repetition (SM-2) + Anki export | ⬜ | `flashcards/` (0-LLM transform) | Flashcards are ideal for an SM-2 scheduler (persist reps/interval/ease) + `.apkg` export — the retention engine for a study app. |
| P6.3 | Click-to-video grounding | ⬜ | `chunking/chunk.py` (timestamps preserved) | Chunks carry segment IDs; store timestamps and let citations/notes jump the player to the exact moment. |
| P6.4 | Multi-lecture organization + sharing | ⬜ | single namespace today | Course collections, public/private share links, per-course tutor contexts. |
| P6.5 | Usage/cost dashboard | ⬜ | Phase P2 metering | Per-user minutes/tokens/cost; transparency justifies pricing. |

---

## Definitions of done

- **P0**: no unauthenticated read of any lecture artifact; webhook rejects unsigned events in prod; uploads size/type-capped; SSRF blocked.
- **P1**: a 22-min lecture's pipeline runs ≤ 25% of current cost/latency; re-running a finished lecture with unchanged inputs costs ~0 API calls. **Validated 2026-08-08** on an ~8-min YouTube lecture: first run = **17 Gemini calls** (15 generateContent + 2 embed batches — extraction was 6 chunks at 15 seg/chunk vs ~40 at the old 5, selector Pass 1 reused the visual analysis, embeds batched 20/call), re-run of the same lecture id = **0 Gemini calls** (every paid stage cache-hit: extraction, outline, visual analysis, screenshot selection, notes artifacts; both Chroma indexes diff-synced with added 0 / removed 0).
- **P2**: quota is enforced before any Gemini spend for anonymous + paid users; lecture status is accurate; badge reflects real usage.
- **P3**: golden-QA MRR/hit-rate tracked per lecture (✅ eval suite + hybrid BM25 in place; calibration threshold sweep covered in `test_evals.py`); citations verified against retrieved chunk IDs (✅); ≥1 improvement to retrieval from P3.2–P3.5 proven by evals (hybrid RRF — `test_hybrid.py` + golden-set regressions).
- **P4**: pipeline survives a backend restart (✅ offline via `backend/test_jobs_restart.py`, 19 checks: stale recovery → re-queue → re-claim → resume-to-complete, exhausted→failed, live-heartbeat untouched, failure-retry semantics); failed runs leave no orphaned dirs; schema changes are versioned.
- **P5**: CI green on every push; clean-install works from `.env.example`; frontend ships split bundles and reports render errors.
- **P6**: streaming is token-level; a flashcard deck exports to Anki; every citation can seek the video.

## Notes on stale docs

- `SAAS_ROADMAP.md` marks webhook verification, quota enforcement, and conversion gates as ✅ — those are non-functional per P0.2/P2. Reconcile the two docs when this roadmap advances.
