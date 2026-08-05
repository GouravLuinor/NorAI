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

## Phase 2 — C (difficulty/quantity) — filter-only
- `backend/main.py:370–389` `/quiz/questions`: add `difficulty` filter over existing generated pool (no regeneration); keep `n`.
- `notes_generator.py:843`: optional bump pipeline default 3 → ~5 for a filterable pool.
- `useQuizStore.ts:156–171`: forward `n` + `difficulty`; `AssessmentView` difficulty selector.

## Phase 3 — E (explain-with-citation + Study Guide)
10. `/quiz/evaluate` (`main.py:392–461`): return per-question stored `explanation`.
11. Cite-on-explain: on explicit "Explain", run `tutor/retriever.retrieve(concepts, chapter_id, output_dir)` → top-1 `source`/`heading_path` (metered only on demand).
12. Frontend: render via `ReferencesPanel`/`buildReferences` (`references.ts:4–29`) + click-to-scroll (`ChatArea.tsx:155–190`); add `citation?` to `Question` (`useQuizStore.ts:16–24`) + "Explain" in `QuizPanel` (`:295–304`) + `assessment-cards.tsx` AnswerKey.
13. **Study Guide** (stretch): aggregate written per-chapter `MergedChapterArtifacts` into a Q&A doc; resume stub `study_pdf_builder`; new doc tab. 

## Deferred design (locked, not built now)
- **B**: backend per-lecture tables `quiz_attempts`/`flashcard_ratings` (mirror `user_threads` init `backend/main.py:92–97`, per-lecture DB `get_lecture_db_path()` `dependencies.py:92–95`) + POST/GET endpoints; frontend persist `FlashcardsPanel` ratings (`:19–20`) + quiz session (`useQuizStore.ts:67–82`) & "review missed" (`{Again,Hard}` filter); pin question batch by attempt id.
- **D** — mind map **derive-first** (no LLM): graph from `lecture_outline.json` (`focus_concepts`/`topics`) + `core_concepts_breakdown`; restore concepts `useChapterStore.ts:41–44`; new `activeDocTab` (`useChapterStore.ts:10`) + tab (`DocPanel.tsx:37–45`); add `react-flow`/`d3`.

## Out of scope (moat track, future)
Timestamp-anchored video player + click-to-seek; deferred audio revision overview.

---

## Verification (post-build)
- `scripts/start-dev.sh` restart (no `--reload`), backend contract probe, `npm run build` + `npm run lint`, browser smoke (Socratic/persona/difficulty/explain), update `PROJECT_PROGRESS.md`.