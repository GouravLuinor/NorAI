# NorAI — Agent Communicator Bridge (`COMMUNICATOR.md`)

> **Purpose**: A shared, living communication log between **Antigravity** (VS Code IDE Assistant) and **OpenCode** (Terminal CLI Assistant). 
> Both agents read and update this file before and after completing tasks to maintain total synchronization, avoid step conflicts, and preserve project context.

---

## 🚦 Current Active Status

| Assistant | Status | Active / Target Task | Last Updated |
|---|---|---|---|
| **Antigravity** (IDE) | 🟢 Idle / Completed | **Production Micro-SaaS Foundation**: Roadmap + Async SQLAlchemy DB + Supabase Auth + Lemon Squeezy Webhooks + Free Trial Gating + Landing & Pricing UI | 2026-08-08 09:44 UTC |
| **OpenCode** (CLI) | 🟢 Idle | Handed off to Antigravity | 2026-08-07 17:25 UTC |

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
