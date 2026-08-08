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
| P1.8 | Adaptive chunking + pre-flight cost estimate | ⏸ | `chunking/chunk.py` | Show users estimated pipeline time/cost before processing; adapt chunk size to lecture length. **Deferred** — the P1 DoD measurement is now in (17 first-run calls / 0 re-run calls for an 8-min lecture), so the pre-flight estimate piece is actionable from real constants; the chunk-adaptation piece needs UX + a default-behavior change. Pick up when scheduling permits. |

---

## Phase P2 — Make billing & quota real

| # | Item | Status | Ref | Notes |
|---|---|---|---|---|
| P2.1 | Increment usage metering | ⬜ | `auth.py:114`, `main.py:958,968` | `used_minutes_this_month` is never incremented anywhere; `UsageLog` never written; `Lecture.duration_seconds` never set. Meter at pipeline end. |
| P2.2 | Enforce quota before download | ⬜ | `backend/main.py:992`, `orchestrator.py:137-151` | Anonymous users skip quota; free-trial gate runs *after* full download. Check first, then consume resources. |
| P2.3 | Persist lecture DB status | ⬜ | `main.py:1015-1025` | `Lecture.status` set to `"processing"` but never updated to `completed/failed`. |
| P2.4 | Live quota badge + `/quota` call | ⬜ | `frontend/src/components/Sidebar.tsx:207-225` | Badge is hardcoded ("Free Trial", "Used: 0 / 15 mins"); frontend never calls `/quota` and never sends the Bearer token for it. |
| P2.5 | Billing page + subscription state UI | ⬜ | — | Surface plan, usage, and Lemon Squeezy checkout/manage links. |

---

## Phase P3 — RAG quality & evals (the moat)

| # | Item | Status | Ref | Notes |
|---|---|---|---|---|
| P3.1 | Golden-QA eval suite | ⬜ | `tutor/` (none exists) | No MRR/hit-rate benchmarks anywhere. Build per-lecture golden sets + MRR/hit-rate tracking; calibrate `CONFIDENCE_THRESHOLD = 0.35` (`retrieval_config.py:48`) with data. |
| P3.2 | Hybrid search + reranking | ⬜ | `tutor/retriever.py:128-137` | Cosine-only, fixed `top_k=5/2`. Add BM25/lexical component and/or cheap reranker; adaptive top-k. |
| P3.3 | Verified citations | ⬜ | `prompts.py:191-205`, `nodes.py:206-213` | Citations are model-generated section names, never post-checked against retrieved chunks. Return chunk IDs from the graph and verify cited sections. |
| P3.4 | Chunk context expansion | ⬜ | `tutor/chunker.py:126-136` | Hits are atomic leaves; no parent-section/sibling pull. Add context window around matches. |
| P3.5 | Cross-turn chapter state | ⬜ | `tutor/nodes_retrieval.py:78-122` | Chapter detection is regex-only and not carried across turns. |
| P3.6 | Fix memory degradation | ⬜ | `tutor/nodes.py:30-31,95-111,251-326` | Transcript grows unboundedly (summaries added, turns never removed); 6-turn window is token-blind; only newest summary kept. Add token budgets + trimming + rolling re-summarization. |
| P3.7 | Graceful low-context handling | ⬜ | `nodes_retrieval.py:247-252`, `nodes.py:189-193` | Retrieval failure returns `[]` with only a prompt-level disclaimer; low-confidence is all-or-nothing (4 good + 1 bad chunks → no flag). |

---

## Phase P4 — Job durability & data layer

| # | Item | Status | Ref | Notes |
|---|---|---|---|---|
| P4.1 | Real job queue | ⬜ | `backend/main.py:1028-1033`, `orchestrator.py:59,117-122` | Unbounded daemon threads, in-memory progress, lost on restart, `_progress` never pruned. Move to DB-backed tasks + worker pool (Dramatiq/RQ) with per-user caps, cancellation, retry, resume. |
| P4.2 | Cleanup on failure | ⬜ | `orchestrator.py:358-377` | Partial lecture dirs, uploads, and keyframes are left on disk on any failure; cleanup is conditional and incomplete. |
| P4.3 | Migrations (Alembic) | ⬜ | `backend/db/database.py:57`, `main.py:138-148` | `create_all` + hand-rolled `ALTER TABLE` with swallowed errors. Adopt Alembic before schema grows. |
| P4.4 | Async tutor persistence | ⬜ | `backend/dependencies.py:126`, `memory.py:19-33` | Per-lecture lock held across the whole `graph.invoke` (sync `SqliteSaver`); one slow turn blocks all chat on that lecture. Use `AsyncSqliteSaver`; evict the unbounded per-lecture graph cache (`dependencies.py:29`). |
| P4.5 | Wire real SSE progress | ⬜ | `orchestrator.py:63-111` | SSE `_queues`/`_event_loop` are dead code — `run_coroutine_threadsafe` targets a loop that's never started. Either implement or drop the scaffolding and keep polling. |

---

## Phase P5 — Foundation

| # | Item | Status | Ref | Notes |
|---|---|---|---|---|
| P5.1 | Observability | ⬜ | `main.py:44-52`, `print()` at `:541,582` | No request IDs, no structured logs, no metrics/tracing, single unrotated `backend.log`. Add structured logging, per-request tracing, LLM token/cost logs, error alerting. |
| P5.2 | Dependency hygiene | ⬜ | `requirements.txt`, no lockfile | Unpinned (`>=`), `streamlit`/`langchain` cruft, **`google-genai` missing** (breaks clean install for `tutor/embedding.py`). Add `.env.example` (with `!.env.example` gitignore exception). |
| P5.3 | CI | ⬜ | no `.github/` | One GH Actions workflow: oxlint, `tsc -b`, `vite build`, run the standalone `test_*.py` scripts. |
| P5.4 | Docker + deploy config | ⬜ | none | `Dockerfile` + compose for local parity; document prod uvicorn/gunicorn + static hosting of `frontend/dist`. |
| P5.5 | Frontend: typed API client | ⬜ | `src/types/index.ts` (32 lines), `apiFetch` returns `null`, 15 `any` sites | Generate types from FastAPI (`openapi-typescript`); single fetch wrapper with auth headers + abort controllers; enable `strict: true`. |
| P5.6 | Frontend: bundle & resilience | ⬜ | 1.34 MB single chunk; no error boundary; `MessageBubble` re-parses markdown on every stream token | Route-level code-splitting, KaTeX lazy load, `React.memo` + Zustand selectors, app-level error boundary + Suspense. |
| P5.7 | Frontend: polling → SSE | ⬜ | `ProcessingPage.tsx:83-104` | 1.5s fixed poll, no backoff/abort, latent extra-request bug on `finished` flip. Replace with real SSE once P4.5 lands; add abort + backoff regardless. |
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
- **P3**: golden-QA MRR/hit-rate tracked per lecture; citations verified against retrieved chunk IDs; ≥1 improvement to retrieval from P3.2–P3.5 proven by evals.
- **P4**: pipeline survives a backend restart; failed runs leave no orphaned dirs; schema changes are versioned.
- **P5**: CI green on every push; clean-install works from `.env.example`; frontend ships split bundles and reports render errors.
- **P6**: streaming is token-level; a flashcard deck exports to Anki; every citation can seek the video.

## Notes on stale docs

- `AGENTS.md` claims pipeline stages "run in subprocesses" and progress "emits via SSE" — neither is true (no `subprocess` usage; `orchestrator.py:11` imports it unused; SSE machinery is dead). Update alongside P4.
- `SAAS_ROADMAP.md` marks webhook verification, quota enforcement, and conversion gates as ✅ — those are non-functional per P0.2/P2. Reconcile the two docs when this roadmap advances.
