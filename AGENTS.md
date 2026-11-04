# AGENTS.md

NorAI: turns a lecture video into study notes, revision notes, assessments, flashcards, and a lecture-grounded AI tutor. Python 3.12 backend (FastAPI) + React 19/TypeScript frontend (Vite).

> Note: this file is NOT mirrored to any other file. CLAUDE.md / GEMINI.md mentioned in an old copy were removed; update this alone.

## Layout

- `config.py` — single source of truth for pipeline constants, model name, output dirs, and `get_api_key()`. Pipeline modules import defaults from here.
- `backend/` — FastAPI app. `main.py` (app factory, lifespan, middleware, static/SPA catch-all; ~850 lines) + `backend/routers/` domain routers (`webhooks`, `billing`, `courses`, `quiz`, `content`, `tutor`) mounted without prefixes so paths are unchanged. Shared helpers live in `backend/access.py` (auth/access checks, guest caps, persona handling, usage flushers) and `backend/lecture_db.py (`_db` + DDL-ensure helpers). `orchestrator.py` runs the pipeline (ingest → `lean/` → tutor index) synchronously inside a `backend/jobs.py` worker thread; progress is persisted to the Lecture DB row and polled by the frontend — no SSE. `backend/gemini_client.py` is the single Gemini client factory + retry/RPM policy used by tutor/, lean/, transcription/.
- `tutor/` — RAG tutor: `graph.py`, `nodes.py`, `nodes_retrieval.py`, `retriever.py`, `indexing.py` (builds the per-lecture index: transcript windows + note sections + screenshots), `vector_store.py` (float16 matrix + docs.json under `outputs/<id>/tutor/index/`, exact cosine), `embedding.py` (`get_embedder`: local EmbeddingGemma or gemini-embedding-2), `local_embedding.py` (on-box ONNX model), `memory.py`, `quiz_nodes.py`. Has its own `config.py` (re-exports root config) and `retrieval_config.py`.
- `lean/` — the pipeline's content stages: compact `[MM:SS]` transcription ∥ keyframes → `structure.py` (one call: title + chapter ranges) → `chapters.py` (one multimodal call per chapter: notes, revision, quiz, screenshot picks). The old 18-stage chain (extract/, visual analysis, merge, chapter-build, screenshot selection) was deleted 2026-10-29; lectures it produced (incl. the `seed_data/` demos) are still read — keep the readers (`backend/video_map.py` `merged_objects/` fallback, notes without `chapter_N.json` `start_sec` in `tutor/indexing.py`).
- `documents/` — non-video intake (PDF/DOCX/PPTX/TXT/MD/web pages/cloud links): extract → transcript-shaped segments with a `loc` label ("p. 4", "Slide 7") → the same `lean/` stages with document wording (`documents/kind.py`). Every server-side fetch of a user URL goes through `documents/fetch.safe_download` (SSRF guard) — never fetch user URLs any other way. Plan + wiring: `docs/INGESTION_PLAN.md`.
- Stage helpers: `ingest/`, `transcription/`, `chunking/`, `visual/` (keyframe-only frame decode + scene detection), `notes/artifacts.py` (writes chapter notes/revision/assessment/flashcards files), `revision_notes/`, `assessment/` (question model), `flashcards/` (SM-2, Anki export).
- `frontend/` — React + TypeScript. `src/stores/` (Zustand), `src/pages/`, `src/components/`, `src/types/`.
- `outputs/` — ALL generated artifacts land here under `outputs/<lecture-id>/` (notes, transcripts, screenshots, tutor index + checkpoints, `backend.log`). Gitignored; treat as throwaway.

## Commands

Dev servers (preferred): `scripts/start-dev.sh {start|stop|status}` — starts BOTH backend (:8000) + frontend (:5173) daemonized, idempotently (won't relaunch over a live port). Logs: `.tmp/dev/backend.log`, `.tmp/dev/frontend.log`.

Backend: `venv/bin/python -m uvicorn backend.main:app --reload --port 8000` — API docs at http://localhost:8000/docs. **Always from repo root with `-m`** (needs `config.py`/`backend` importable; use the `venv/` env).

Frontend: `cd frontend && npm run dev` (Vite on :5173).

### Dev-server gotchas (these burned a QA pass — read before touching servers)
- Health-check by **HTTP probe** (`curl http://127.0.0.1:8000/docs`), NEVER by reading a uvicorn log file. A healthy uvicorn at `--log-level warning` writes nothing — a 0-byte log does NOT mean down.
- If a port is already serving, **reuse it**. Relaunching over an occupied port makes uvicorn spin at ~120% CPU in a bind-retry loop (looks "stuck", burns CPU). `start-dev.sh start` is idempotent for exactly this reason.
- Launch backend from repo root with `-m uvicorn`. Running `python /tmp/.../script.py` that does `uvicorn.Config('backend.main:app')` fails with `No module named 'backend'` (script dir, not repo root, is on `sys.path`).
- **No `/usr/bin/npm` on this machine** — npm lives under nvm. Always `$(command -v npm)` or rely on `start-dev.sh`.

Lint is **oxlint**, NOT eslint: `cd frontend && npm run lint`.

Build: `npm run build` (= `tsc -b && vite build`).

Tests: there is NO test framework/pytest. Tests are standalone `test_*.py` scripts (e.g. `tutor/test_chunker.py`, `assessment/test_schema.py`) run directly: `python tutor/test_chunker.py`. Run the whole offline suite (+ pyflakes on backend/) with `scripts/run-tests.sh`. Integration tests for full lecture runs don't exist.

## Environment & model config

- `GEMINI_API_KEY` is required (root `config.py:get_api_key()` raises `ValueError` if absent). Loaded from `.env` via python-dotenv. `.env` is gitignored — never commit it.
- Model defaults live ONLY in root `config.py`: `MODEL_NAME = "gemini-3.1-flash-lite"`, `TEMPERATURE = 0.4`, retry/RPM limits. The separate `tutor/config.py` re-exports these so the tutor and core stay in sync.
- Overload handling (`backend/gemini_client.py`, knobs in `config.py`): `NORAI_MODEL` swaps the model for one run without editing the default. Every Gemini request through the shared client times out after `NORAI_GEMINI_TIMEOUT_SEC` (240 s) and is retried by the policy. After `NORAI_FALLBACK_AFTER_503S` (2) consecutive 503s from the primary model, `generate_content` goes to `NORAI_FALLBACK_MODEL` (`gemini-3.5-flash-lite`; empty = off) for `NORAI_FALLBACK_COOLDOWN_SEC` (300 s). Not covered: calls bound to a context cache, streaming, and the tutor chat (LangChain, not the shared client). Fallback calls are metered under the primary model's name in the usage log.
- Embeddings (768 dims, `tutor/retrieval_config.py`): new indexes use the **local** `embeddinggemma-300m-q4` (ONNX, `tutor/local_embedding.py`; no API quota, ~75 CPU-s for a 52-min lecture on 1 thread). `NORAI_EMBEDDING_MODEL=gemini-embedding-2` switches back to Gemini (better on Hinglish, but the free tier's 100/min + daily cap runs out). Each index records its `model` in docs.json (none = legacy Gemini) and queries are embedded with that lecture's model, so both kinds coexist. Distances aren't comparable across models: the relevance/image thresholds are per model (`confidence_threshold()`, `image_max_distance()`). Model files (~210 MB) download once into `.models/` (gitignored; `NORAI_EMBED_MODEL_DIR`), or `venv/bin/python -m tutor.local_embedding --download`; the Docker image bakes them in. gemini-embedding-2 does NOT accept `task_type=`; older Gemini embedding models (001/-exp) are deprecated — don't introduce them.
- No Chroma: `chromadb` was removed. A leftover `tutor/chroma/chroma.sqlite3` only counts as "index done" (`has_tutor_index`); the real index is built lazily on the first question. Re-index a lecture with `venv/bin/python -m tutor.indexing outputs/<id>` (content-hashed, only new docs are embedded; a different embedding model rebuilds the whole index).
- **Run mode & intake sources** (`config.py`; plan in `docs/INGESTION_PLAN.md`): one codebase, two settings, no edition branches. `NORAI_MODE=local` = single-user install on a PC (no login, no quotas, SQLite; `scripts/setup-local.sh` writes it); `hosted` (default) = Supabase + quotas. `NORAI_SOURCES` = allowed intake sources (local default: all; hosted default: `gdrive,upload,link`, YouTube off). Check ownership/quota bypasses with `config.dev_access()`, never by reading `NORAI_DEV_ACCESS` directly. The UI reads both from `GET /system/config`. Keep YouTube code working (local uses it); turn it off by config, don't delete it.
- CORS in `backend/main.py` is deliberately broad (all common Vite ports). Keep it broad during dev.

## Conventions / gotchas

- All pipeline stages do real LLM/API calls against Gemini (paid/token-metered). Don't run the full pipeline casually or repeatedly for testing — check with the user first.
- Lecture IDs propagate via output dirs, not shared globals; there is no `subprocess` usage anywhere — the pipeline runs in a job-queue worker thread. Keep lecture isolation when editing.
- `outputs/` and `.tmp/` are regenerable intermediates — never commit them.
- Personal opencode scripting notes live in `opencode-guide/` (gitignored) — not project docs.

## Tooling workflow (opencode + Antigravity)

The developer splits heavy work between opencode and **Google Antigravity** (Gemini **3.7 Flash, high thinking mode**, via the Google AI Pro subscription). Git is the handoff point: whoever finishes commits/stashes, then the other resumes.

- **Antigravity (3.7 Flash, high) owns:** big refactors & architecture, greenfield codegen, large-context work (1M window), and hard debugging. Output should be commits/PRs or pasted diffs/plans.
- **opencode owns:** surgical single-file edits, mechanical changes, tool-heavy agentic loops (running tests/lint/builds, `start-dev.sh`, dev-server smoke tests, Chrome DevTools MCP), and quick QA.
- **Handoff:** keep AGENTS.md authoritative; git commits plus `docs/PROJECT_PROGRESS.md` carry the state (no separate handoff log).
- **Antigravity limits (AI Pro):** compute-based usage, refresh every 5h, capped weekly; heavy `high`-mode burns fast. Don't waste it on trivial edits — those go to opencode.

> Do NOT try to use the Google AI subscription from opencode directly: the `opencode-gemini-auth` OAuth plugin was blocked by Google on 2026-06-18 for AI Pro/Ultra accounts, and there is no API-key access for this subscription. If asked to set up Gemini in opencode, use a Google AI Studio API key (`google/gemini-3.7-flash`), never the OAuth plugin.

## Agent model notes (image analysis)

- The default agent runs on a **text-only** model (e.g. deepseek v4 flash) that CANNOT see/analyze images. When a task needs image analysis — screenshots, UI snapshots, charts/figures, visual diffs, OCR of images — do NOT try to read the image directly; delegate to a subagent running the **MiMo V2.5 Free** model via the `opencode-subagents` skill.
- MiMo V2.5 Free is Xiaomi's omnimodal model (text + image + video + audio understanding), available free on OpenCode Zen under the id `opencode/mimo-v2.5-free` (dots — the hyphenated `mimo-v2-5-free` id causes server errors). Pass the image path(s) to the subagent and have it return written findings.

## Docs

`README.md` (architecture + pipeline), `docs/PROJECT_PROGRESS.md` (living current-state doc — update when making notable pipeline/backend/frontend changes), `docs/PHASE2_REPORT.md` (legacy vs lean pipeline before/after: cost, quality, server load), `docs/NOTES.md` (developer notes: fix log, pricing/decisions, open items), `docs/DEPLOYMENT_PLAN.md` (agreed production deployment path — Hostinger VPS, single-container, Caddy, Supabase), `docs/NotebookLM_competitive_analysis.md` (forward feature ideas), `docs/INGESTION_PLAN.md` (local vs hosted editions + multi-format intake plan and step status), `docs/ROADMAP.md` (phased engineering-hardening plan — security → economics → billing → RAG → durability → foundation → retention; update item status as work lands).

`docs/TUTORIAL.md` (full-project tutorial + interview prep) — agents do NOT need to read it for working on the codebase; it's large and would fill the context window unnecessarily. Only update it from time to time when significant changes land, to keep it in sync with the project.