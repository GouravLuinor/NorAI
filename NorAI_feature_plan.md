# NorAI — Feature Implementation Plan (NotebookLM parity)

Source: `NotebookLM_competitive_analysis.md` Part 4 (recommended roadmap). All A–F features verified feasible against the codebase. Decisions locked by user (Aug 2026).

## Scope
- **Implement now (High-value first):** A (Socratic Study mode) + F (custom persona), C (difficulty/quantity), E (explain-with-citation + Study Guide).
- **Deferred (designed):** B (quiz/flashcard persistence), D (concept/mind map).

## Cost posture (agreed)
- Selectors **filter** the generated pool; never regenerate by default (metered).
- Citations resolve only on an explicit "Explain" click (meter-bound).

---

## Phase 1 — A + F (tutor mode + persona) — build together, one prompt path

Shared single prompt-assembly site: `tutor/prompts.py:7` `TUTOR_SYSTEM_PROMPT` → `build_system_prompt()` (`prompts.py:312`) → injected `tutor/nodes.py:163,183–189`, seeded from `input_state` at `backend/dependencies.py:135–141`.

**Backend**
1. `tutor/state.py` — add `study_mode: str`, `persona_instructions: str` to `ChatState` (replace-reducer, auto-persisted per-thread). Defaults `"default"`, `""`.
2. `tutor/prompts.py` — add `SOCRATIC_SYSTEM_PROMPT` constant; extend `build_system_prompt(lecture_title, mode="default")`.
3. `tutor/nodes.py:163,183–189` — read state mode/persona; append extra `SystemMessage` when persona non-empty; select Socratic base prompt by mode.
4. `tutor/nodes_retrieval.py` — leave rewrite/summarizer prompts fixed.
5. `backend/main.py:137–142` `ChatRequest` + `backend/dependencies.py:100–193` — accept & thread `study_mode`/`persona` into `input_state`.

**Frontend**
6. `useQuizStore.ts:40` — extend `aiMode` union → `'socratic'`.
7. `AIPanel.tsx:29–84` — 4th "Study" segment + `onChange` + dispatch; `Workspace.tsx:15–71` widths.
8. Persona settings modal in `AIPanel.tsx:52` (reuse `Dialog`), persist lecture-scoped via `threadStorage.ts` pattern, send `mode`/`persona` via `chatApi.ts:46–52`.

## Phase 2 — C (difficulty/quantity) — filter-only ✓ Done
- `backend/main.py:377-397` `/quiz/questions`: added `difficulty` query param (case-insensitive `Easy|Medium|Hard`); pre-filters the generated pool before the existing `n` sample. No regeneration (keeps cost posture).
- `useQuizStore.ts`: exported `QuizDifficulty` type; `fetchQuizQuestions` forwards `difficulty`; `startQuiz` persists `quizDifficulty`, `retakeQuiz` re-filters with it.
- `AssessmentView.tsx`: `All/Easy/Medium/Hard` selector refetches the list + Start Quiz; empty-state covers a 0-result difficulty; filter resets on lecture change.
- `backend/test_api_contract.py`: added a `/quiz/questions?difficulty=Easy` shape check.
- Note: the original "bump pipeline default 3 → ~5 for a filterable pool" was stale — `assessment_prompts.py:133-139` already targets 8–10 questions/chapter (models enforce 4–15). No generator/prompt change; existing pools are filter-only (a given difficulty may return 0 on a small pool, handled by the UI empty-state).

## Phase 3 — E (explain-with-citation + Study Guide) ✓ Done
- **Cite-on-explain**: `POST /quiz/explain` (`main.py`) — on-demand single retrieval (top-1 note chunk + top-1 screenshot) via `tutor/retriever.retrieve`; returns `{source, heading, heading_path, chapter_id, text, screenshot}` or a graceful `source:null` (missing index) — one embedding call, never regenerates. Frontend: `explainQuizQuestion` helper (`useQuizStore.ts`), shared `CitationBox` component, `lib/cite.ts` click-to-scroll (sets chapter + revision tab + poll-scroll, mirrors ChatArea). Explain affordance in **QuizPanel** (feedback branch) + **AssessmentView** (per-card, `assessment-cards.tsx` `QuestionCard` gained `onExplain`).
- **Study Guide (zero-run)**: `GET /study-guide` catalogs already-generated `revision_chapter_<id>.md` in chapter order (`{title, chapters:[{chapter_id,title,markdown}]}`) — pure file reads, no LLM. Frontend: new `StudyGuideView` + `'guide'` doc tab (`useChapterStore`/`DocPanel` segment 06); Guide PDF maps to the `revision` print type (same content, all chapters).
- `backend/test_api_contract.py`: added `/study-guide` shape + `POST /quiz/explain` probes using the first real lecture id.
- Note: the plan's "resume stub `study_pdf_builder`" was stale — no such file exists; Study Guide is assembled client/backend-side from existing artifacts (locked: zero-run, no drill).
- Note: question `explanation` was already stored + shown (AnswerKey / QuizPanel feedback), so E's "return stored explanation" needed no work — the gap was source grounding, now filled.

## Phase 4 — B (Quiz & Flashcard Persistence + History UI) ✓ Done
- Backend: added `quiz_attempts` & `flashcard_ratings` tables to per-lecture SQLite DB with zero-LLM metadata endpoints (`POST /quiz/attempts`, `POST /quiz/attempts/{id}/finish`, `GET /quiz/attempts`, `GET /quiz/attempts/{id}/missed`, `POST /flashcards/ratings`, `GET /flashcards/ratings`).
- Frontend: `useQuizStore.ts` tracks attempt state; `FlashcardsPanel.tsx` uses SHA-256 card keys (`lib/hash.ts`), persists rating updates to backend, and adds an "Again/Hard Missed Only" deck filter toggle; `QuizPanel.tsx` eval screen adds "Review Missed" action; `AssessmentView.tsx` adds a "Questions / History" segmented control with attempt history cards and "Retake Missed" buttons.
- `backend/test_api_contract.py`: added probe assertions for all 5 new endpoints.

## Phase 5 — D (Mind Map / Concept Map per Chapter) ✓ Done
- Backend: added zero-LLM endpoint `GET /concept-map` (`backend/main.py`) deriving 3-tier hierarchical nodes and edges from existing `lecture_outline.json` & `notes_chapter_<id>.json` at $0 API cost.
- Frontend: `useChapterStore.ts` widened `activeDocTab` to include `'concepts'`; `DocPanel.tsx` added segment `07 Mind map`; new interactive `ConceptMapView.tsx` component with SVG bezier curved paths, tree/radial layout toggle, pan/zoom controls, concept selection detail card, and "Ask Nora about this concept" integration with `useThreadStore`.
- `backend/test_api_contract.py`: added probe check for `/concept-map`.

## Out of scope (moat track, future)
Timestamp-anchored video player + click-to-seek; deferred audio revision overview.

---

## Verification (post-build)
- `scripts/start-dev.sh` restart (no `--reload`), backend contract probe, `npm run build` + `npm run lint`, browser smoke (Socratic/persona/difficulty/explain), update `PROJECT_PROGRESS.md`.