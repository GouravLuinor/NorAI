# AGENTS.md

NorAI: turns a lecture video into study notes, revision notes, assessments, flashcards, and a lecture-grounded AI tutor. Python 3.12 backend (FastAPI) + React 19/TypeScript frontend (Vite).

> Note: this file is NOT mirrored to any other file. CLAUDE.md / GEMINI.md mentioned in an old copy were removed; update this alone.

## Layout

- `config.py` — single source of truth for pipeline constants, model name, output dirs, and `get_api_key()`. Pipeline modules import defaults from here.
- `backend/` — FastAPI app. `main.py` (all routes inline; `backend/routers/` is empty and unused) + `orchestrator.py` (runs the full 18-stage pipeline synchronously inside a `backend/jobs.py` worker thread; progress is persisted to the Lecture DB row and polled by the frontend — no SSE).
- `tutor/` — RAG tutor: `graph.py`, `nodes.py`, `nodes_retrieval.py`, `retriever.py`, `embedding.py` (custom Chroma embedding fn for gemini-embedding-2), `memory.py`, `quiz_nodes.py`. Has its own `config.py` (re-exports root config) and `retrieval_config.py`.
- One pipeline-stage dir each: `ingest/`, `transcription/`, `chunking/`, `extract/`, `visual/`, `notes/`, `revision_notes/`, `assessment/`, `flashcards/`, `retrieval/`, `vectordb/`.
- `frontend/` — React + TypeScript. `src/stores/` (Zustand), `src/pages/`, `src/components/`, `src/types/`.
- `outputs/` — ALL generated artifacts land here under `outputs/<lecture-id>/` (notes, transcripts, chapters, screenshots, tutor checkpoints, chroma DB, `backend.log`). Gitignored; treat as throwaway.

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

Tests: there is NO test framework/pytest. Tests are standalone `test_*.py` scripts (e.g. `tutor/test_chunker.py`, `assessment/test_schema.py`) run directly: `python tutor/test_chunker.py`. Integration tests for full lecture runs don't exist.

## Environment & model config

- `GEMINI_API_KEY` is required (root `config.py:get_api_key()` raises `ValueError` if absent). Loaded from `.env` via python-dotenv. `.env` is gitignored — never commit it.
- Model defaults live ONLY in root `config.py`: `MODEL_NAME = "gemini-3.1-flash-lite"`, `TEMPERATURE = 0.4`, retry/RPM limits. The separate `tutor/config.py` re-exports these so the tutor and core stay in sync.
- Embeddings use `gemini-embedding-2` (768 dims), configured in `tutor/retrieval_config.py`. It does NOT accept `task_type=`; task instructions go in the prompt. Older embedding models (gemini-embedding-001/-exp) are deprecated — don't introduce them.
- Chroma persistent store defaults to `outputs/tutor/chroma`, overridable via `NORAI_CHROMA_DIR`.
- CORS in `backend/main.py` is deliberately broad (all common Vite ports). Keep it broad during dev.

## Conventions / gotchas

- All pipeline stages do real LLM/API calls against Gemini (paid/token-metered). Don't run the full pipeline casually or repeatedly for testing — check with the user first.
- Lecture IDs propagate via output dirs, not shared globals; there is no `subprocess` usage anywhere — the pipeline runs in a job-queue worker thread. Keep lecture isolation when editing.
- `outputs/` and `.tmp/` are regenerable intermediates — never commit them.
- Personal opencode scripting notes live in `opencode-guide/` (gitignored) — not project docs.

## Agent model notes (image analysis)

- The default agent runs on a **text-only** model (e.g. deepseek v4 flash) that CANNOT see/analyze images. When a task needs image analysis — screenshots, UI snapshots, charts/figures, visual diffs, OCR of images — do NOT try to read the image directly; delegate to a subagent running the **MiMo V2.5 Free** model via the `opencode-subagents` skill.
- MiMo V2.5 Free is Xiaomi's omnimodal model (text + image + video + audio understanding), available free on OpenCode Zen under the id `opencode/mimo-v2.5-free` (dots — the hyphenated `mimo-v2-5-free` id causes server errors). Pass the image path(s) to the subagent and have it return written findings.

## Docs

`README.md` (architecture + pipeline), `PROJECT_PROGRESS.md` (living current-state doc — update when making notable pipeline/backend/frontend changes), `COMMUNICATOR.md` (shared agent handoff bridge — check and update after completing tasks), `NOTES.md` (developer notes: fix log, pricing/decisions, open items), `NotebookLM_competitive_analysis.md` (forward feature ideas), `audit/audit_tutor_and_auxiliary.md` (tutor/RAG/frontend audit detail), `ROADMAP.md` (phased engineering-hardening plan — security → economics → billing → RAG → durability → foundation → retention; update item status as work lands).

`TUTORIAL.md` (full-project tutorial + interview prep) — agents do NOT need to read it for working on the codebase; it's large and would fill the context window unnecessarily. Only update it from time to time when significant changes land, to keep it in sync with the project.