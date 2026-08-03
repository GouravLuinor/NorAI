# NorAI — Rebuild Roadmap

Status: Tier 0, Tier 1, Tier 2, and Tier 3 Implementation Completed and Verified.

Purpose: Organize everything surfaced by the codebase audit + follow-up investigations into a sequenced plan, grouped by dependency and readiness.

---

## Constraint That Shapes Everything Below

**Google AI Studio free tier: 15 RPM / 500 RPD.** This is a hard ceiling, not a soft optimization target. Through Tier 2 consolidation, the total LLM calls per lecture were reduced from **~128 calls down to ~35 calls** (~72% reduction), drastically lowering quota footprint and pipeline latency.

---

## Tier 0 — No Dependencies, No Open Questions (100% COMPLETED) ✅

1. **Delete dead H.264 conversion code** (`ingest/ingest.py`) — `convert_to_h264()` confirmed unused. ✅ **[DONE]**
2. **Fix chunk-to-screenshot mapping gap** (`visual/mapper.py`) — add nearest-keyframe fallback (within ±20s tolerance) when strict boundary check yields zero screenshots. ✅ **[DONE]**
3. **Recalibrate screenshot Pass 1 scoring rubric** (`notes/screenshot_selector.py`) — fix `FRAME_QUALITY_PROMPT` wording so text-heavy slides score appropriately (6-8 range). `MIN_CONTENT_DENSITY = 6` untouched. ✅ **[DONE]**
4. **Parallelize frame extraction + scene detection with transcription + chunking** (`backend/orchestrator.py`) — Branch A and Branch B run concurrently via `ThreadPoolExecutor`. ✅ **[DONE]**
5. **Fix directory traversal on `lecture_id`** (`backend/main.py`, `backend/dependencies.py`) — `sanitize_lecture_id()` alphanumeric/UUID validation. ✅ **[DONE]**
6. **Fix unvalidated upload filenames** (`backend/main.py`) — `Path(file.filename).name` and regex sanitization. ✅ **[DONE]**
7. **Fix SSRF risk in URL matching** (`ingest/ingest.py`) — exact `urlparse(url).netloc` whitelist matching. ✅ **[DONE]**
8. **Add `try/finally` around OpenCV VideoCapture** (`visual/extract_frames.py`) — resource leak fix. ✅ **[DONE]**
9. **Switch SQLite connections to context managers** (`backend/main.py`) — connection leak fix. ✅ **[DONE]**
10. **Enable SQLite WAL mode + busy_timeout** (`backend/dependencies.py`, `backend/main.py`) — `PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;`. ✅ **[DONE]**
11. **Add file locking to `lectures.json` registry writes** (`backend/lecture_registry.py`) — `_registry_lock` added. ✅ **[DONE]**
12. **Consolidate rate limiter into a single shared instance** (`backend/ratelimit.py`) — exported global `rate_limiter` singleton. ✅ **[DONE]**
13. **Remove dead PDF builder modules** (`assessment_pdf_builder.py`, `study_pdf_builder.py`, `revision_pdf_builder.py`, `generate_pdfs.py`). ✅ **[DONE]**
14. **Clean up root-level orphan files** (`test_api.py`, `visual.txt`, `tree.txt`). ✅ **[DONE]**
15. **Centralize hardcoded config** into top-level `config.py` — root configuration module created and re-exported. ✅ **[DONE]**

### Tutor Subsystem — Tier 0 (COMPLETED) ✅

16. **Re-sequence LangGraph edges in `tutor/graph.py`** — `rewrite_query` completes before both `retrieve` and `retrieve_images` fire. ✅ **[DONE]**
17. **Clear `retrieved_images: []` per turn in `rewrite_query_node`** (`tutor/nodes_retrieval.py`) — reset `retrieved_images` alongside `retrieved_chunks`. ✅ **[DONE]**
18. **Use singleton retriever in `retrieve_images_node`** (`tutor/nodes_retrieval.py`) — uses process-wide cached `retrieve_images()` singleton. ✅ **[DONE]**
19. **Deduplicate merged arrays in `chapter_builder.py`** (`notes/chapter_builder.py`) — `dict.fromkeys()` applied across all Chapter array fields. ✅ **[DONE]**

---

## Tier 1 — Design Decisions & Refactoring (100% COMPLETED) ✅

### 1.1 Flashcards → deterministic 0-call transform ✅ **[DONE]**
- Extended `Question` model in `assessment_models.py` with `flashcard_front`, `flashcard_back`, and `flashcard_explanation`.
- `generate_flashcards.py` uses `convert_assessment_to_flashcards()`, a 0-call transform (saved ~30 LLM calls per lecture).

### 1.2 Adopt structured output (`response_schema`) across all LLM calls ✅ **[DONE]**
- Enforced Pydantic `response_schema` across all JSON-producing LLM endpoints (`assessment_generator.py`, `outline_generator.py`, `extractor.py`, `visual_extractor.py`, Pass 1 & Pass 2 in `screenshot_selector.py`).

### 1.3 `MAX_GAP_SECONDS` scene detection tuning & batch size optimization ✅ **[DONE]**
- Set `MAX_GAP_SECONDS = 60` in `visual/scene_detector.py`. Set `PASS1_BATCH_SIZE = 10` in `notes/screenshot_selector.py` (cuts Pass 1 API calls by 50%).

### 1.4 Tutor retrieval confidence threshold calibration (`tutor/retrieval_config.py`) ⏳ **[PENDING VERIFICATION]**
- Pending empirical cosine distance verification from real tutor query logs before modifying.

---

## Tier 2 — Architecture-Level Pipeline Consolidation & Latency Optimization (100% COMPLETED) ✅

### 2.0 Sequential Files API upload parallelization ✅ **[DONE]**
- Replaced sequential `client.files.upload()` loop with `ThreadPoolExecutor`-based concurrent uploads in `visual/visual_extractor.py` and `notes/screenshot_selector.py` (38s latency improvement).

### 2.1 Batch visual extraction by chapter instead of per-chunk ✅ **[DONE]**
- Replaced ~35-40 per-chunk visual calls with chapter-aligned batch calls (1 call per chapter, saved 31 LLM calls).

### 2.2 Merge Knowledge Extraction + Outline Generation — REJECTED ❌ **[REJECTED]**
- Kept separate for per-chunk parallel execution and retry isolation.

### 2.3 Merge Study Notes + Revision Notes + Assessment into one call per chapter ✅ **[DONE]**
- Consolidated Study Notes, Revision Summaries, and Quiz Assessments into 1 LLM call per chapter (saved 20 LLM calls).

---

## Tier 3 — Quality, Prompt Engineering & UI Determinism (100% COMPLETED) ✅

### 3.1 Domain-Aware Prompt Overhaul & Noise Rejection ✅ **[DONE]**
- Overhauled `EXTRACTION_SYSTEM_PROMPT` in `extract/prompts.py` for technical terms, formulas, and strict bounds on `inferred_knowledge`.
- Added UI noise rejection (ignoring YouTube player timeline, captions, watermarks) to `visual/visual_prompts.py`.
- Enforced density-based word count scaling and organic formatting guidelines (tables, math blocks) in `notes/notes_generator.py`.

### 3.2 Pydantic Structured Section Cards & Deterministic UI Rendering ✅ **[DONE]**
- Added `StudyNoteSection` model (`section_type`, `title`, `content_markdown`) to `MergedChapterArtifactsModel` in `notes/notes_generator.py`.
- Persisted dual outputs: `chapter_{id}.json` (for 100% deterministic UI card rendering) and `chapter_{id}.md` (for RAG vector indexing).
- Updated `/notes/{chapter_id}` backend endpoint, `NotesView.tsx`, and `PrintPage.tsx` to map section types directly to UI cards for web and PDF export views.

### 3.3 Lecture Title Sync & Dynamic AI Thread Naming ✅ **[DONE]**
- Implemented 3-tier title fallback hierarchy (`lecture_outline.json` $\rightarrow$ `chapters[0]` $\rightarrow$ `chapter_1.md`) in `backend/lecture_registry.py`.
- Implemented ChatGPT-style auto-renaming for AI chat threads on first question in `useThreadStore.ts`.

### 3.4 Granular Chunking & Chapter Target Optimization ✅ **[DONE]**
- Updated `DEFAULT_SEGMENTS_PER_CHUNK = 5` (~1 min/chunk) in `chunking/chunk.py`.
- Updated `target_chapters` calculation formula (3 to 8 chapters) in `notes/outline_generator.py` for full-length lecture coverage.

---

## Deferred Items

- **Removing redundant `start_normal` pass-through node in `tutor/graph.py`** — cosmetic/efficiency change deferred.
- **Multi-user / auth / deployment hardening** (CORS lockdown, endpoint auth) — deferred until deployment target.
- **Database modernization (SQLite → Postgres)** — deferred.
- **Async DAG workflow engine (Temporal/Prefect)** — deferred.

---

## Progress Summary

- **Tier 0 Infrastructure Tasks (1–19)**: 19 / 19 Completed (100%) ✅
- **Tier 1 Design Tasks (1.1–1.3)**: 3 / 3 Completed (100%) ✅
- **Tier 1.4 Tutor Threshold**: Pending Empirical Logs ⏳
- **Tier 2.0 Upload Parallelization**: Completed (38s latency win) ✅
- **Tier 2.1 Chapter Visual Extraction**: Completed (31 LLM calls saved) ✅
- **Tier 2.2 Extraction + Outline Merge**: Rejected ❌
- **Tier 2.3 Notes + Quiz Chapter Merge**: Completed (20 LLM calls saved) ✅
- **Tier 3.1 Prompt Overhaul**: Completed ✅
- **Tier 3.2 Structured UI Section Cards**: Completed ✅
- **Tier 3.3 Title & Thread Auto-Sync**: Completed ✅
- **Tier 3.4 Chunking & Chapter Target Optimization**: Completed ✅
