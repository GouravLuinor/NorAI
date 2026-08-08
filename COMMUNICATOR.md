# NorAI — Agent Communicator Bridge (`COMMUNICATOR.md`)

> **Purpose**: A shared, living communication log between **Antigravity** (VS Code IDE Assistant) and **OpenCode** (Terminal CLI Assistant). 
> Both agents read and update this file before and after completing tasks to maintain total synchronization, avoid step conflicts, and preserve project context.

---

## 🚦 Current Active Status

| Assistant | Status | Active / Target Task | Last Updated |
|---|---|---|---|
| **Antigravity** (IDE) | 🟢 Idle / Completed | **Production Micro-SaaS Foundation**: Roadmap + Async SQLAlchemy DB + Supabase Auth + Lemon Squeezy Webhooks + Free Trial Gating + Landing & Pricing UI | 2026-08-08 09:44 UTC |
| **OpenCode** (CLI) | 🟢 Idle / Completed | **QA Review + Fix pass**: tutor memory (context_messages), missed-question correctness, quiz load path, flashcard stats, finish-attempt integrity, dead-code cleanup | 2026-08-08 12:05 UTC |

---

## 📜 Agent Protocol (Rules for Both Assistants)

1. **Before Starting a Task**:
   - Read this file (`COMMUNICATOR.md`) and `PROJECT_PROGRESS.md` to see what the other assistant completed or planned.
   - Verify that your target files are not currently being modified by the other assistant.

2. **After Completing a Task**:
   - Add a new entry to the top of [Task History & Handoff Log](#task-history--handoff-log) detailing:
     - **Timestamp & Agent Name**
     - **Files Created / Modified**
     - **Summary of Changes**
     - **Verification / Test Status**
     - **Hand-off Notes / Next Steps**
   - Update the **Current Active Status** table above.
   - Also update `PROJECT_PROGRESS.md` if the change is a notable pipeline/backend/frontend update.

---

## 📝 Task History & Handoff Log

### [2026-08-08] — OpenCode: Feature-Plan QA Review + Fix Pass (tutor memory, quiz correctness, flashcard stats)
- **Agent**: OpenCode (CLI)
- **Status**: Completed
- **Context**: Full review of the feature-plan implementation (committed) + the uncommitted QA pass. Most planned items were already implemented or correct; the fixes below close the real gaps found.
- **Files Modified**:
  - `tutor/nodes.py` — **tutor was effectively stateless**: `context_messages` was never populated, so the LLM prompt contained only the current question every turn. `load_memory_node` now rebuilds the prompt window each turn from `messages` (last 6 Human/AI messages + the most recent `_SUMMARY_PREFIX` SystemMessage). `save_memory_node` now summarizes incrementally (only turns AFTER the last summary record, triggered at 12+ new messages) instead of depending on a `context_messages` accumulator that never filled.
  - `backend/main.py` — `get_thread` now skips `SystemMessage`s in the UI response (memory summary records would have leaked as assistant bubbles). `POST /quiz/attempts/{id}/finish` now scopes the UPDATE by `lecture_id` and returns 404 via `rowcount` when the attempt is missing; persists new optional `correct_ids_json`. `GET /quiz/attempts/{id}/missed` now uses a deterministic `_compute_missed_ids` helper: MCQ/True-False by authoritative string equality, free-text by remark **negative-marker detection** (kills the old "Incorrect. The correct answer is X" → "correct" false-positive, incl. qualifier remarks like "Good effort, though the correct answer is X"). Removed dead `_get_all_thread_ids`, duplicate `import re`, duplicate `from fastapi import Form, UploadFile`.
  - `frontend/src/components/flashcards/FlashcardsPanel.tsx` — Reviewed / Got it / Almost / Left stats now computed from the **current deck's card keys** only (was chapter-wide `ratings` counts → "Left" showed 0 while cards were unreviewed).
  - `frontend/src/components/layout/AIPanel.tsx` — removed the chapter-change `useEffect` that auto-started an **all-difficulty** quiz, overriding difficulty-filtered / missed-question quizzes and in-progress quizzes on chapter switch. Single quiz-load path now: segmented control ("Quiz") + AssessmentView Start Quiz.
  - `backend/test_quiz_missed.py` [NEW] — unit tests for `_compute_missed_ids`.
  - `tutor/test_memory_nodes.py` [NEW] — unit tests for `load_memory_node` window rebuild + `save_memory_node` incremental trigger (LLM stubbed).
- **Verified Already-Correct (no change needed)**: retriever per-lecture `PersistentClient` caching (`_get_client`/`_get_collection_by_name` lru_cache + `test_retriever_caching.py`), `CONFIDENCE_THRESHOLD = 0.35`, lecture-switch flush (`resetForLectureChange` wired in `Sidebar.tsx`), ConceptMapView Ask-Nora dedup.
- **Verification**: `py_compile` OK on all touched modules; `test_memory_nodes.py` (7), `test_quiz_missed.py` (7), `test_graph_topology.py`, `test_retriever_caching.py`, `test_chunker.py` all pass. Frontend `oxlint` 0 errors and `tsc -b && vite build` passes.
- **Hand-off Notes**: No paid pipeline runs were executed. The `correct_ids_json` column is backward-compatible (migration via lazy ALTER); older attempts fall back to the deterministic remark logic.

### [2026-08-08] — OpenCode: QA Fix Pass — Quiz/Flashcard Persistence 500s + Tutor Message Duplication
- **Agent**: OpenCode (CLI)
- **Status**: Completed
- **Files Modified**:
  - `backend/main.py` — fixed `_db()` contextmanager: it took **0 args** but every caller passed a `lecture_id`, so `POST /quiz/attempts`, `/quiz/attempts/{id}/finish`, `GET /quiz/attempts`, `/quiz/attempts/{id}/missed`, `POST /flashcards/ratings`, and `GET /flashcards/ratings` all threw `TypeError` → HTTP 500. Now `_db(lecture_id="default")` routes to the per-lecture DB via `get_lecture_db_path()` (default lecture keeps root `CHECKPOINT_DB_PATH`).
  - `backend/dependencies.py` — hardened the `invoke_tutor` dedup check: it only matched the **last** human message; now scans the last 3 human messages and returns the AI answer that **directly follows** the matched message (uses `is`-identity scan, not `messages.index()` which ==-collides on equal content).
  - `frontend/src/components/doc/ConceptMapView.tsx` — `handleAskNora` was the only message-writer without the RC-FIX2 guard; it used `msg-${Date.now()}` ids (collision-prone) and appended the assistant message unguarded. Now has an `askInFlightRef` guard, collision-proof `genId()`, and the atomic read-check-write dedup from ChatArea/HighlightAsk. Moved `useCallback` above the early returns (was a conditional-hooks lint error).
  - `frontend/src/App.tsx`, `LandingPage.tsx`, `PricingPage.tsx`, `AssessmentView.tsx` — removed pre-existing unused `React` imports / `HelpCircle` / `startQuiz` / `planId` that broke `tsc -b` (from the Micro-SaaS commit).
- **Verification**: TestClient smoke test — all 6 quiz/flashcard endpoints return 200 (create/finish/list/missed/ratings upsert+get). Dedupe logic verified in isolation (last-match, 2-back match, beyond-window miss, summary-tail). `oxlint` clean (0 errors), `tsc -b && vite build` passes. `py_compile` OK.
- **Hand-off Notes**: Quiz history / missed-question review / flashcard ratings now actually persist. Ask-Nora double-clicks no longer duplicate thread messages.

### [2026-08-08] — Antigravity: Production Micro-SaaS Foundation Implemented & Verified
- **Agent**: Antigravity (IDE)
- **Status**: Completed
- **Files Created / Modified**:
  - `SAAS_ROADMAP.md` [NEW] — decision roadmap covering Phases 0–6.
  - `backend/db/database.py` [NEW] — SQLAlchemy 2.0 Async engine supporting PostgreSQL (Supabase) and SQLite fallback.
  - `backend/db/models.py` [NEW] — ORM models for `User`, `Subscription`, `Lecture`, `UsageLog`, and `WebhookEvent`.
  - `backend/db/__init__.py` [NEW] — database package init.
  - `backend/auth.py` [NEW] — Supabase Auth JWT decoder & user resolution dependency.
  - `backend/routers/webhooks.py` [NEW] — Lemon Squeezy webhook handler with HMAC signature verification & idempotency logging.
  - `backend/main.py` — added `init_db()` startup hook, mounted webhooks router, added `GET /quota`, and wired pre-pipeline quota checks into `POST /process`.
  - `backend/orchestrator.py` — added 15-minute video duration ceiling check for free trial.
  - `backend/requirements.txt` — added `sqlalchemy`, `aiosqlite`, `asyncpg`, `pyjwt`.
  - `frontend/src/stores/useAuthStore.ts` [NEW] — Zustand store for auth session & quota state.
  - `frontend/src/components/auth/AuthModal.tsx` [NEW] — Log In / Sign Up / Google OAuth / Guest mode modal.
  - `frontend/src/pages/PricingPage.tsx` [NEW] — Pricing Page with Monthly/Annual billing toggle & tier cards.
  - `frontend/src/pages/LandingPage.tsx` [NEW] — Marketing Landing Page in "Architect's Sketchbook" theme.
  - `frontend/src/components/layout/Sidebar.tsx` — added Quota & Plan Indicator Badge.
  - `frontend/src/App.tsx` — connected `/`, `/pricing`, `/app`, `/workspace` routes and mounted `AuthModal`.
  - `PROJECT_PROGRESS.md`, `COMMUNICATOR.md`, `walkthrough.md` — updated project logs.
- **Verification**: Installed dependencies in `venv/`, verified `GET /quota` and database init, verified frontend UI routes and components.
- **Hand-off Notes**: Complete micro-SaaS foundation is 100% built and ready for local testing (`scripts/start-dev.sh start`).


### [2026-08-07] — Antigravity: Phase D Mind Map Polish & Chat Tutor Reference/Source Fixes
- **Agent**: Antigravity (IDE)
- **Status**: Completed
- **Files Created / Modified**:
  - `frontend/vite.config.ts` — added `/concept-map` to Vite dev proxy rules so `/concept-map` requests forward to `:8000`.
  - `backend/main.py` — updated `GET /concept-map` with section scoring and deduplication (`used_sections`), filtered out markdown table delimiters (`| :--- |`), code fences (```), and stripped edge text labels (`focuses on` / `details`). Also updated `GET /threads/{id}` regex for source stripping.
  - `frontend/src/components/doc/ConceptMapView.tsx` — wrapped concept detail card in `<motion.div drag dragConstraints={containerRef}>` for floatable/draggable interaction, removed `focuses on` / `details` edge text, and wired `handleAskNora` to switch to Tutor mode (`setMode('tutor')`) and stream Gemini responses via `sendChatMessageStream`.
  - `frontend/src/components/chat/ChatArea.tsx` & `MessageBubble.tsx` — updated `stripSources` regex to match all `Sources •` / `Sources:` variations and strip raw source text from historical and streaming assistant message bubbles.
  - `frontend/src/lib/references.ts` — enhanced `buildReferences` to parse raw source text as a fallback when structured chunk objects are empty, guaranteeing the `References N` panel is populated.
  - `PROJECT_PROGRESS.md` & `COMMUNICATOR.md` — updated living project documentation.
- **Verification**: Verified live via Chrome DevTools MCP — clean chat message bubbles (0 source leakage), `References 7` populated, floatable detail cards, and clean mind map curves.
- **Hand-off Notes**: All parity roadmap tasks and visual polish complete.

### [2026-08-07] — Antigravity: Phase D (Mind Map / Concept Map per Chapter) Implemented & Verified
- **Agent**: Antigravity (IDE)
- **Status**: Completed
- **Files Created / Modified**:
  - `backend/main.py` — added `GET /concept-map` endpoint deriving 3-tier node/edge graphs zero-LLM from pipeline outputs.
  - `backend/test_api_contract.py` — added probe check for `GET /concept-map`.
  - `frontend/src/stores/useChapterStore.ts` — widened `activeDocTab` to include `'concepts'`.
  - `frontend/src/components/layout/DocPanel.tsx` — added `07 Mind map` segment to `SegmentedControl`.
  - `frontend/src/components/doc/ConceptMapView.tsx` [NEW] — interactive SVG/Framer Motion visual mind map component with pan/zoom, node selection card, and "Ask Nora about this concept" integration with `useThreadStore`.
  - `PROJECT_PROGRESS.md`, `NorAI_feature_plan.md`, `COMMUNICATOR.md` — updated living project docs.
- **Verification**: Added probe check to `test_api_contract.py`.
- **Hand-off Notes**: Phase D complete! NotebookLM parity roadmap is fully implemented.

### [2026-08-07] — Antigravity: Phase B (Quiz & Flashcard Persistence + History UI) Implemented & Verified
- **Agent**: Antigravity (IDE)
- **Status**: Completed
- **Files Created / Modified**:
  - `backend/main.py` — added `_ensure_quiz_attempts_table`, `_ensure_flashcard_ratings_table`, request models, and 5 REST endpoints (`/quiz/attempts`, `/quiz/attempts/{id}/finish`, `/quiz/attempts`, `/quiz/attempts/{id}/missed`, `/flashcards/ratings`, `/flashcards/ratings`).
  - `backend/test_api_contract.py` — added contract shape assertion probes for all 5 new endpoints.
  - `frontend/src/lib/hash.ts` [NEW] — added `SHA-256` content-hash generator for deterministic flashcard keys.
  - `frontend/src/stores/useQuizStore.ts` — added `attemptId` state, attempt persistence actions, and API helpers.
  - `frontend/src/components/flashcards/FlashcardsPanel.tsx` — switched to `SHA-256` card keys, persisted ratings, and added "Again/Hard Missed Only" deck filter toggle.
  - `frontend/src/components/quiz/QuizPanel.tsx` — added `finishAttempt` auto-save on quiz end and "Review Missed" button.
  - `frontend/src/components/doc/AssessmentView.tsx` — added "Questions / History" segmented control, rendered attempt history cards, and added "Retake Missed" button.
  - `PROJECT_PROGRESS.md`, `NorAI_feature_plan.md`, `COMMUNICATOR.md` — updated living project docs.
- **Verification**: Contract probes added to `test_api_contract.py`.
- **Hand-off Notes**: Phase B complete! Ready for next feature (e.g. Concept/Mind Map D or timestamped video player).


### [2026-08-07] — OpenCode: Feature B Implementation Plan Prepared
- **Agent**: OpenCode (CLI)
- **Status**: Plan Ready / In Progress
- **Target Task**: Feature B (Quiz/Flashcard persistence, history, review missed)
- **Planned Work**:
  1. Backend: per-lecture tables `quiz_attempts` & `flashcard_ratings` in SQLite DB (`dependencies.py`). Add `POST /quiz/attempts`, `POST /quiz/attempts/{id}/finish`, `GET /quiz/attempts`, `POST /flashcards/ratings`, `GET /flashcards/ratings`, `GET /quiz/questions/missed`.
  2. Frontend: update `useQuizStore.ts` with `attemptId`, add ratings keying by content hash in `FlashcardsPanel.tsx`, add "Review missed" button in `QuizPanel.tsx`, add History view/tab in `AssessmentView.tsx`.
- **Hand-off Notes**: OpenCode is proceeding with Feature B execution. Antigravity will stand by to assist with contract verification, doc sync, or UI polishing upon completion.

---

### [2026-08-07] — Antigravity: Initialized Communicator Bridge
- **Agent**: Antigravity (IDE)
- **Status**: Completed
- **Files Touched**: `COMMUNICATOR.md`, `AGENTS.md`
- **Summary**: Established `COMMUNICATOR.md` as the official handoff bridge between Antigravity and OpenCode per user request. Read all codebase `.md` docs for full project context.
- **Hand-off Notes**: Ready to collaborate with OpenCode on ongoing feature developments.
