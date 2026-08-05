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

- **Phase 1 of the NotebookLM parity roadmap: tutor Study (Socratic) mode + custom persona.** Backend `ChatState` gained `study_mode` + `persona_instructions`; `tutor/prompts.py` added `SOCRATIC_SYSTEM_PROMPT` + `build_system_prompt(title, mode)`; `tutor/nodes.py` appends a persona `SystemMessage` when non-empty; `ChatRequest` + `invoke_tutor` thread both fields through `/chat` and `/chat/stream`. Frontend: `aiMode` widened to include `socratic`, new `Study` segment in the AI panel, per-lecture persona persists via `useTutorSettingsStore` (localStorage) and a `PersonaModal`. Delivered against `NorAI_feature_plan.md` (A+F).
- **Backend ↔ frontend contract sync** (post-rebuild): `/quiz/questions` now returns `{"questions": [...], "incomplete": bool}`; removed dead `_load_quiz_questions` and orchestrator-local `update_lecture_title` shadow; `invoke_tutor` treats lecture id `default`/empty as the global graph. Frontend: options-driven generic question cards, `fetchQuizIncomplete` + `PartialContentBadge` in AssessmentView, `ProcessingPage` STAGES aligned to the real backend chain. Added standalone `backend/test_api_contract.py`.
- **Frontend design rebuild (Tier 0–5)**: "Architect's Sketchbook" theme; a11y/Web-Guidelines pass (Lighthouse a11y 100 both themes); signature typography pass; dark-mode "Luminous Blueprint at Night". Roadmap complete.
- **Tier 2 pipeline consolidation**: Files-API parallelization, chapter-batched visual extraction, merged chapter-artifact generation, screenshot selection remapping. ~72% call reduction.

## Pointers

- `AGENTS.md` — always-loaded instructions, commands, conventions.
- `README.md` — architecture + pipeline detail.
- `context.md` — compact project/rebuild context.
- `NotebookLM_competitive_analysis.md` — forward feature ideas (flashcard persistence, quiz history).
- `NorAI_feature_plan.md` — staged NotebookLM-parity roadmap (A–F); Phase 1 (A+F) done.
- `audit/audit_tutor_and_auxiliary.md` — retained tutor/RAG/frontend audit detail.
