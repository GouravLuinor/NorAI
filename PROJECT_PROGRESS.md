# NorAI — Project Progress (living current-state doc)

> Condensed from the original per-week changelog (recoverable from git history). Update this file whenever you make a notable pipeline/backend/frontend change. The single always-loaded instruction file is `AGENTS.md`; this doc is the project's current-state snapshot.

## Vision

NorAI turns a long lecture video into a complete study experience: structured study notes, revision notes / cheat sheets, assessments, flashcards, and a lecture-grounded AI tutor (RAG over the lecture's text + screenshots).

## Current Architecture

```
Video (YouTube / upload / Drive)
  → Ingestion (audio extract, metadata)
  → Transcription (faster-whisper, timestamped segments)
  → Chunking (segment→chunk, timestamps preserved)
  → Knowledge Extraction (transcript → structured knowledge objects)
  → Frame Extraction + Scene Detection (parallel with transcription/chunking)
  → Chunk ↔ Screenshot Mapping
  → Outline Generation
  → Visual Knowledge Extraction (per-chapter, batched)
  → Knowledge Merging
  → Chapter Building
  → Screenshot Selection
  → Chapter Artifacts (study notes + revision + assessment + flashcards, 1 call/chapter)
  → Tutor + Screenshot Indexing (Chroma)
  → Cleanup
```

- **Backend**: FastAPI (`backend/main.py`, all routes inline) + `backend/orchestrator.py` runs the pipeline async and emits progress via SSE.
- **Tutor**: LangGraph RAG (`tutor/`) — per-lecture graph isolation, persistent multi-thread memory (SQLite checkpoints), parallel text+screenshot retrieval, tool calling, quiz workflows, flashcards.
- **Frontend**: React 19 + TypeScript + Vite, three-panel workspace (doc pane / chat / AI panel), Zustand stores, Tailwind v4. Design theme: **"Architect's Sketchbook"** (warm vellum light default + Prussian-blue dark, Space Grotesk + Newsreader, red-pencil accents).

## Model & config truth (source of truth: root `config.py`)

- `MODEL_NAME = "gemini-3.1-flash-lite"`, `TEMPERATURE = 0.4`, `GEMINI_API_KEY` from `.env` (required).
- Embeddings: `gemini-embedding-2` (768 dims) via custom Chroma embedding fn in `tutor/embedding.py` (`tutor/retrieval_config.py`). No `task_type=` arg; instructions go in the prompt.
- Chroma store: `outputs/tutor/chroma` (override `NORAI_CHROMA_DIR`).
- Free-tier ceiling: **15 RPM / 500 RPD** — pipeline consolidated from ~128 → ~35 LLM calls per lecture.

## Output layout

All artifacts land under `outputs/<lecture-id>/` (notes, revision, assessment, screenshots, flashcards, pdfs, tutor checkpoints, chroma, `backend.log`). Gitignored / throwaway.

## What's built (feature checklist)

- **Pipeline**: 18-stage orchestrator with SSE progress; concurrent transcription/chunking + frame/scene extraction; graceful degradation (partial-content marker) on retry failures.
- **Per-lecture isolation**: lecture registry (`backend/lecture_registry.py`), per-lecture tutor graphs + checkpoints + Chroma indexes + thread history; backward-compatible default/global tutor mode.
- **Tutor**: grounded Q&A with citations + timestamps, chapter-aware routing, query rewriting, confidence-aware answers, persistent multi-thread conversations, highlight-and-ask, references panel, screenshot previews.
- **Resources**: study notes, revision notes, assessments, quiz engine (start/answer/evaluate), flashcards, chapter screenshots, PDF export (notes/revision).
- **Frontend**: workspace with resizable panels (keyboard-accessible), doc tabs (notes/revision/assessment), Quiz mode + flashcard "Cards" mode in the AI panel, search, print/PDF, dark mode toggle, math rendering (KaTeX), shortcuts modal.

## Recent changes

- **Landing/Pricing page review pass (frontend-design + Web Interface Guidelines + MiMo screenshot QA).** Fixed a critical typography bug: `LandingPage.tsx`/`PricingPage.tsx` used numeric `text-*` utilities (`text-12/15/17/18/20/22/28/36/44`, plus invalid `*-bold`/`*-regular`/`*-medium` combos) that were **not defined in `@theme`** — verified absent from compiled CSS, so the entire type scale silently collapsed to 16px. Added `--text-10…44` tokens to `index.css` `@theme` and rewrote the `*-bold` classes as `text-<size> font-bold`. A11y/compliance: skip link (`App.tsx` → `id="main"` on all page roots), `scroll-margin-top` for `#features`/`#how-it-works`, Pricing nav `<button>`→`<Link>`, removed dead `#privacy`/`#terms` anchors, mobile nav menu (hamburger + `aria-expanded`), ARIA tabs pattern on the workspace mockup (`role="tablist"/tab/tabpanel` + roving tabindex + arrow/Home/End), `role="switch"`+`aria-checked` billing toggle, `tabular-nums` on prices, `text-balance` on headings, reduced-motion respected via global `<MotionConfig reducedMotion="user">` (framer animations previously ignored `prefers-reduced-motion`), `transition-all`→explicit properties, decorative grid `aria-hidden`. Copy: deduped pricing h1, tightened free-plan tagline, curly apostrophe. MiMo (opencode/mimo-v2.5-free) screenshot QA surfaced a real mobile overflow: the mockup tabs bar's nowrap min-content (~477px) widened the section past the 390px viewport and got clipped by `overflow-x-hidden`; fixed with `w-full` on the mockup section + `overflow-x-auto` tabs bar + title truncate + mobile-hidden status badge. `npm run build` (tsc) + `oxlint` green; verified tokens/roles present in compiled `dist/`; visual re-QA: all screens PASS.
- **Feature-plan QA review + fix pass.** Full review of `NorAI_feature_plan.md` deliverables; the real gaps found were fixed. **(1) Tutor memory** — `context_messages` was never populated, so the LLM prompt was effectively stateless (current question only). `tutor/nodes.py` `load_memory_node` now rebuilds the prompt window each turn from `messages` (last 6 Human/AI + most recent `_SUMMARY_PREFIX` summary); `save_memory_node` summarizes incrementally (turns after the last summary, triggered at 12+ new messages); `get_thread` skips `SystemMessage`s so summary records never leak into the UI. **(2) Missed-question correctness** — `GET /quiz/attempts/{id}/missed` now uses a deterministic `_compute_missed_ids` (MCQ/True-False by string equality, free-text by remark negative-marker detection) instead of the substring search that marked "Incorrect. The correct answer is X" as correct. `finish_quiz_attempt` is lecture-scoped with a `rowcount` 404 and persists optional `correct_ids_json` (lazy-ALTER migration). **(3) Quiz load path** — removed the `AIPanel` chapter-change effect that auto-started an all-difficulty quiz, overriding difficulty-filtered / missed-question / in-progress quizzes; single entry via segmented control + AssessmentView Start Quiz. **(4) Flashcard stats** — Reviewed/Got it/Almost/Left now computed from the current deck's card keys (was chapter-wide). **(5) Cleanup** — removed dead `_get_all_thread_ids` + duplicate imports. New tests: `backend/test_quiz_missed.py`, `tutor/test_memory_nodes.py`. Verified already-correct: retriever per-lecture client caching, `CONFIDENCE_THRESHOLD=0.35`, lecture-switch flush, ConceptMap Ask-Nora dedup. All Python tests + `oxlint` + `tsc -b && vite build` green; no paid pipeline runs.
- **QA fix pass — quiz/flashcard persistence 500s + tutor message duplication.** `backend/main.py` `_db()` took 0 args but every quiz/flashcard caller passed a `lecture_id` → all 6 persistence endpoints (`POST /quiz/attempts`, `/quiz/attempts/{id}/finish`, `GET /quiz/attempts`, `/quiz/attempts/{id}/missed`, `POST /flashcards/ratings`, `GET /flashcards/ratings`) threw `TypeError`/500. `_db(lecture_id="default")` now routes to the per-lecture DB (`get_lecture_db_path`; default keeps root `CHECKPOINT_DB_PATH`). `backend/dependencies.py` dedup now scans the last 3 human messages (was only the last) and returns the AI answer directly following the matched message via identity scan (was `messages.index()` ==-collision-prone). `ConceptMapView.handleAskNora` gained the RC-FIX2 atomic dedup + in-flight ref + collision-proof `genId()` (was the only unguarded message writer, using `msg-${Date.now()}`). Removed pre-existing unused declarations (`App/LandingPage/PricingPage` React imports, `HelpCircle`, `startQuiz`, `planId`) that broke `tsc -b`.
- **Production Micro-SaaS Foundation (Phases 0–6 Roadmap & Core Infrastructure)**: Created full SaaS productization decision roadmap ([SAAS_ROADMAP.md](file:///home/gourav/coding/VScode/Projects/NorAI/SAAS_ROADMAP.md)) and implementation plan. Built backend database architecture (`backend/db/database.py`, `backend/db/models.py`) with SQLAlchemy 2.0 async engine supporting Supabase Postgres and local SQLite. Created `User`, `Subscription`, `Lecture`, `UsageLog`, and `WebhookEvent` models. Implemented Supabase Auth JWT verification (`backend/auth.py`), Lemon Squeezy payment webhook handler with HMAC signature verification & idempotency logging (`backend/routers/webhooks.py`), startup DB initialization in `backend/main.py`, and free trial 15-minute video duration validation in `backend/orchestrator.py`.
- **Phase D of the NotebookLM parity roadmap: Mind Map / Concept Map per chapter & Tutor chat fixes.** Backend: added zero-LLM endpoint `GET /concept-map` (`backend/main.py`) deriving hierarchical 3-tier node/edge graphs from `lecture_outline.json` & `notes_chapter_<id>.json` at $0 token cost. Added section scoring & deduplication (`used_sections`), filtered markdown table delimiters (`| :--- |`), code fences (```), and stripped edge text labels. Frontend: `useChapterStore.ts` widened `activeDocTab` to include `'concepts'`; `DocPanel.tsx` added segment `07 Mind map`; new interactive `ConceptMapView.tsx` component with SVG bezier curved paths, tree/radial layout toggle, pan/zoom controls, floatable/draggable node detail card (`motion.div drag`), and streaming "Ask Nora about this concept" integration. `stripSources` regex updated in `ChatArea.tsx` & `MessageBubble.tsx` to eliminate raw source leakage, and `buildReferences` in `lib/references.ts` enhanced with text fallback parsing to guarantee `References N` count population. `vite.config.ts` proxy updated with `/concept-map`. Standalone test suite (`backend/test_api_contract.py`) expanded with `/concept-map` probe check.

- **Phase B of the NotebookLM parity roadmap: quiz & flashcard persistence + history UI.** Added per-lecture SQLite tables `quiz_attempts` & `flashcard_ratings` (`backend/main.py`) with zero-LLM metadata endpoints (`POST /quiz/attempts`, `POST /quiz/attempts/{id}/finish`, `GET /quiz/attempts`, `GET /quiz/attempts/{id}/missed`, `POST /flashcards/ratings`, `GET /flashcards/ratings`). Frontend: `useQuizStore.ts` tracks attempt state; `FlashcardsPanel.tsx` uses deterministic `SHA-256` content-hash keying (`lib/hash.ts`), persists rating updates to backend, and adds an "Again/Hard Missed Only" deck filter toggle; `QuizPanel.tsx` eval screen adds "Review Missed" action; `AssessmentView.tsx` adds a "Questions / History" segmented control with attempt history cards and "Retake Missed" buttons. Automated contract test suite (`backend/test_api_contract.py`) expanded to verify all 5 new endpoints.
- **Phase 3 of the NotebookLM parity roadmap: explain-with-citation + Study Guide (E).** New `POST /quiz/explain` (`backend/main.py`) resolves a question's source with a single on-demand retrieval (`tutor/retriever.retrieve`, top-1 note chunk + screenshot) — one embedding call, never regenerates; graceful `source:null` on a missing index. Frontend: `explainQuizQuestion` + shared `CitationBox` + `lib/cite.ts` click-to-scroll; "Explain · where is this in the notes?" in both `QuizPanel` and `AssessmentView` (`QuestionCard` `onExplain`). New `GET /study-guide` catalogs the already-generated per-chapter revision markdown into one doc (pure file reads); new `Guide` doc tab renders it via `StudyGuideView`, PDF maps to the revision print type. Contract test gained `/study-guide` + `/quiz/explain` probes.
- **Phase 2 of the NotebookLM parity roadmap: quiz difficulty filter (C).** `/quiz/questions` (`backend/main.py`) takes an optional `difficulty` (`Easy|Medium|Hard`, case-insensitive) that pre-filters the generated pool before the `n` sample — pure read, no regeneration (keeps cost posture). Frontend: `useQuizStore` forwards `difficulty`, and `startQuiz`/`retakeQuiz` persist/filter by the active difficulty; `AssessmentView` gained an `All/Easy/Medium/Hard` selector that refetches the list + Start Quiz and resets on lecture change. `backend/test_api_contract.py` gained a `difficulty=Easy` shape check. The plan's "bump pipeline default to 5" step was stale (prompts already target 8–10/chapter) and was dropped.
- **Phase 1 of the NotebookLM parity roadmap: tutor Study (Socratic) mode + custom persona.** Backend `ChatState` gained `study_mode` + `persona_instructions`; `tutor/prompts.py` added `SOCRATIC_SYSTEM_PROMPT` + `build_system_prompt(title, mode)`; `tutor/nodes.py` appends a persona `SystemMessage` when non-empty; `ChatRequest` + `invoke_tutor` thread both fields through `/chat` and `/chat/stream`. Frontend: `aiMode` widened to include `socratic`, new `Study` segment in the AI panel, per-lecture persona persists via `useTutorSettingsStore` (localStorage) and a `PersonaModal`. Delivered against `NorAI_feature_plan.md` (A+F).
- **Backend ↔ frontend contract sync** (post-rebuild): `/quiz/questions` now returns `{"questions": [...], "incomplete": bool}`; removed dead `_load_quiz_questions` and orchestrator-local `update_lecture_title` shadow; `invoke_tutor` treats lecture id `default`/empty as the global graph. Frontend: options-driven generic question cards, `fetchQuizIncomplete` + `PartialContentBadge` in AssessmentView, `ProcessingPage` STAGES aligned to the real backend chain. Added standalone `backend/test_api_contract.py`.
- **Frontend design rebuild (Tier 0–5)**: "Architect's Sketchbook" theme; a11y/Web-Guidelines pass (Lighthouse a11y 100 both themes); signature typography pass; dark-mode "Luminous Blueprint at Night". Roadmap complete.
- **Tier 2 pipeline consolidation**: Files-API parallelization, chapter-batched visual extraction, merged chapter-artifact generation, screenshot selection remapping. ~72% call reduction.

## Pointers

- `AGENTS.md` — always-loaded instructions, commands, conventions.
- `README.md` — architecture + pipeline detail.
- `context.md` — compact project/rebuild context.
- `NotebookLM_competitive_analysis.md` — forward feature ideas (flashcard persistence, quiz history).
- `NorAI_feature_plan.md` — staged NotebookLM-parity roadmap (A–F); Phase 1 (A+F), Phase 2 (C), Phase 3 (E) done.
- `audit/audit_tutor_and_auxiliary.md` — retained tutor/RAG/frontend audit detail.
