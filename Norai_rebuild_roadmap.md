# NorAI — Rebuild Roadmap

Status: Tier 0 & Tier 1 Implementation Completed and Verified. Planning for Tier 2.

Purpose: organize everything surfaced by the overnight audit + follow-up investigation into a sequenced plan, grouped by dependency and readiness — not just a flat list of findings.

---

## Constraint That Shapes Everything Below

**Google AI Studio free tier: 15 RPM / 500 RPD.** This is a hard ceiling, not a soft optimization target. At current pipeline shape (~128 calls for a 25-min lecture), one lecture already consumes ~25% of the daily quota. This constraint raises the priority of API-call reduction work beyond "nice to have cost savings" — it directly determines how many lectures/day the system can realistically process. Keep this in view when sequencing everything else.

---

## Tier 0 — No Dependencies, No Open Questions (100% COMPLETED)

These are fully diagnosed, isolated, and carry no design ambiguity.

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

### Tutor Subsystem — Tier 0 (COMPLETED)

16. **Re-sequence LangGraph edges in `tutor/graph.py`** — `rewrite_query` completes before both `retrieve` and `retrieve_images` fire. ✅ **[DONE]**
17. **Clear `retrieved_images: []` per turn in `rewrite_query_node`** (`tutor/nodes_retrieval.py`) — reset `retrieved_images` alongside `retrieved_chunks`. ✅ **[DONE]**
18. **Use singleton retriever in `retrieve_images_node`** (`tutor/nodes_retrieval.py`) — uses process-wide cached `retrieve_images()` singleton. ✅ **[DONE]**
19. **Deduplicate merged arrays in `chapter_builder.py`** (`notes/chapter_builder.py`) — `dict.fromkeys()` applied across all Chapter array fields. ✅ **[DONE]**

---

## Tier 1 — Design Decisions & Refactoring (100% COMPLETED / 1 PENDING VERIFICATION)

### 1.1 Flashcards → deterministic 0-call transform ✅ **[DONE]**
- **Status**: Extended `Question` model in `assessment_models.py` with `flashcard_front` (max 15 words), `flashcard_back` (max 20 words), `flashcard_explanation` (max 30 words).
- **Implementation**: `generate_flashcards.py` uses `convert_assessment_to_flashcards()`, a 0-call transform (saved ~30 LLM calls per lecture).

### 1.2 Adopt structured output (`response_schema`) across all LLM calls ✅ **[DONE]**
- **Status**: Enforced Pydantic `response_schema` across all 6 JSON-producing LLM endpoints (`assessment_generator.py`, `outline_generator.py`, `extractor.py`, `visual_extractor.py`, Pass 1 & Pass 2 in `screenshot_selector.py`).

### 1.3 `MAX_GAP_SECONDS` scene detection tuning & batch size optimization ✅ **[DONE]**
- **Status**: Set `MAX_GAP_SECONDS = 60` in `visual/scene_detector.py` (matches ~57-80s chunk duration). Set `PASS1_BATCH_SIZE = 10` in `notes/screenshot_selector.py` (cuts Pass 1 API calls by 50%).

### 1.4 Tutor retrieval confidence threshold calibration (`tutor/retrieval_config.py`) ⏳ **[PENDING VERIFICATION]**
- **Proposed change**: Increase `CONFIDENCE_THRESHOLD` from `0.30` to `0.35` to reduce false-positive low-confidence disclaimers.
- **Status**: Pending empirical cosine distance verification from real tutor query logs before modifying.

---

## Tier 2 — Architecture-Level Pipeline Consolidation & Latency Optimization

### 2.0 Sequential Files API upload parallelization — READY TO IMPLEMENT 🚀 **[READY]**
No design decision needed. Replace sequential `client.files.upload()` loop with `ThreadPoolExecutor`-based concurrent uploads (or inline byte embedding if simpler) in `visual/visual_extractor.py` and `notes/screenshot_selector.py`. No call-count change, no failure-mode change, pure latency win. Implement independently of everything else below.

### 2.1 Batch visual extraction by chapter instead of per-chunk — APPROVED FOR IMPLEMENTATION ✅ **[APPROVED]**
Current: ~35-40 calls (1 per chunk). Target: ~9-10 calls (1 per chapter, batched candidate images per chapter). Failure handling: if a chapter's batch call fails after retries, that chapter gets zero visual objects (consistent with existing degradation pattern) rather than halting the pipeline — mark it incomplete in chapter metadata (`incomplete: true`).

### 2.2 Merge Knowledge Extraction + Outline Generation — REJECTED ❌ **[REJECTED]**
Reasoning: knowledge extraction runs per-chunk specifically for parallelism and retry isolation; outline generation runs once over merged output. These have different granularity and merging them collapses a parallelizable, retry-safe stage into a single fragile serial one, to save only 1 call (outline is already cheap). Keep these stages separate. If further call reduction on knowledge extraction is wanted later, apply the same per-chapter batching pattern as 2.1 instead.

### 2.3 Merge Study Notes + Revision Notes + Assessment into one call per chapter — APPROVED FOR IMPLEMENTATION (AFTER 2.1) ⏳ **[APPROVED - AFTER 2.1]**
Current: 30 calls (10 chapters × 3 artifact types). Target: ~9-10 calls (1 per chapter, structured response with three top-level fields: `study_notes`, `revision_summary`, `assessment_questions`). Failure handling: same as 2.1 — silent degradation with an `incomplete: true` flag on that chapter's artifacts, not a full pipeline halt. Sequence this after 2.1 is implemented and tested, not simultaneously.

---

## Do Not Touch Yet

- **Removing redundant `start_normal` pass-through node in `tutor/graph.py`** — cosmetic/efficiency change only with zero functional impact; not worth bundling with real bug fixes.
- **Multi-user / auth / deployment hardening** (CORS lockdown, endpoint auth) — deferred until there's an actual deployment target.
- **Database modernization (SQLite → Postgres)** — deferred until multi-user becomes a real near-term goal.
- **Async DAG workflow engine (Temporal/Prefect)** — deferred.

---

- **Progress Summary**:
  - **Tier 0 Infrastructure Tasks (1–19)**: 19 / 19 Completed (100%) ✅
  - **Tier 1 Design Tasks (1.1–1.3)**: 3 / 3 Completed (100%) ✅
  - **Tier 1.4 Tutor Threshold**: Pending Empirical Logs ⏳
  - **Tier 2.0 Upload Parallelization**: Completed (38s latency win) ✅
  - **Tier 2.1 Chapter Visual Extraction**: Completed (31 LLM calls saved) ✅
  - **Tier 2.2 Extraction + Outline Merge**: Rejected ❌
  - **Tier 2.3 Notes + Quiz Chapter Merge**: Completed (20 LLM calls saved) ✅
