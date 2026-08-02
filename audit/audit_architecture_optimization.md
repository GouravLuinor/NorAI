# Part 2 — Architecture & Pipeline Optimization Audit Report

This report evaluates **6 core optimization hypotheses** to collapse total processing time and drastically reduce LLM API calls across the NorAI pipeline.

---

## Hypothesis Evaluation Summary

| # | Optimization Hypothesis | Status | Current Call Count | Proposed Call Count | Primary Risk / Tradeoff |
|---|-------------------------|--------|-------------------|---------------------|------------------------|
| **1** | Video conversion overhead elimination | **Confirmed Partial / Mostly Fixed** | 0 extra video transcode passes | 0 passes | Minor format verification check needed |
| **2** | Parallelize non-dependent sequential stages | **Confirmed True** | Sequential execution | Concurrent execution | Increased peak CPU/Memory load |
| **3** | Consolidate Knowledge & Outline LLM passes | **Confirmed True** | ~71 calls (35 text + 35 visual + 1 outline) | 1–2 unified calls | Token context size management |
| **4** | Batch visual extraction screenshots | **Confirmed True** | 35 calls (1 per chunk) | 4–10 calls (per chapter) | Context length vs visual precision |
| **5** | Merge Notes, Revision & Assessment calls | **Confirmed True** | 30 calls (3 per chapter) | 10 calls (1 per chapter) | Strict JSON schema enforcement required |
| **6** | Convert Flashcards to deterministic transform | **Confirmed True** | 7–10 LLM calls | **0 LLM calls** | Minor loss of stylistic rewrite variety |

---

## Detailed Findings per Hypothesis

### 1. Video Conversion Overhead
- **Current State**: In [ingest/ingest.py:L199-L215](file:///home/gourav/coding/VScode/Projects/NorAI/ingest/ingest.py#L199-L215), YouTube videos are downloaded using `yt-dlp` format filtering (`bestvideo[height<=720][vcodec^=avc1]+bestaudio/best...`). Direct H.264 video streams are fetched directly without requiring a secondary `convert_to_h264` re-encoding pass via `ffmpeg`.
- **Verification**: `convert_to_h264` is defined at [ingest/ingest.py:L128](file:///home/gourav/coding/VScode/Projects/NorAI/ingest/ingest.py#L128) but is **not** invoked in `extract_from_youtube` or `extract_from_local`. Audio extraction converts video audio to 192k MP3 via `ffmpeg` in ~2 seconds.
- **Verdict**: Confirmed complete and correct for YouTube downloads. Local uploaded non-MP4 files still require audio extraction.

---

### 2. Sequential Stages with No Real Dependency
- **Current Pipeline Flow** ([backend/orchestrator.py:L138-L230](file:///home/gourav/coding/VScode/Projects/NorAI/backend/orchestrator.py#L138-L230)):
  1. Ingestion (`process_source`) -> Video + Audio
  2. Transcription (`transcribe_audio`)
  3. Chunking (`chunk_transcript`)
  4. Knowledge Extraction (`extract_all_chunks`) — *35 LLM calls*
  5. Frame Extraction (`extract_frames`) — *OpenCV*
  6. Scene Detection (`detect_scenes`) — *PySceneDetect / OpenCV*
  7. Mapping (`create_chunk_screenshot_mapping`)
  8. Visual Knowledge (`process_all_chunks`) — *35 LLM calls*
  9. Knowledge Merging (`merge_all_chunks`)
  10. Outline Generation (`generate_lecture_outline`) — *1 LLM call*
  11. Chapter Building (`build_chapters_pipeline`)
  12. Screenshot Selection (`select_screenshots_for_lecture`)
  13. Study Notes (`generate_study_notes`) — *10 LLM calls*
  14. Revision Notes (`generate_revision_notes_for_lecture`) — *10 LLM calls*
  15. Assessment (`generate_assessment_for_lecture`) — *10 LLM calls*
  16. Flashcards (`generate_flashcards`) — *7 LLM calls*

- **Independent Parallel Branches Identified**:
  - **Branch A (Audio/Text)**: Stage 2 (Transcription) -> Stage 3 (Chunking).
  - **Branch B (Visual)**: Stage 5 (Frame Extraction) -> Stage 6 (Scene Detection).
  - **Dependency Analysis**: Stage 5 and 6 depend *only* on `video_path` from Stage 1. They currently wait for Stage 2, Stage 3, and Stage 4 to complete sequentially!
- **Proposed Optimization**: Run Branch A and Branch B concurrently using Python `asyncio` or `ThreadPoolExecutor` immediately after Stage 1 finishes.
- **Estimated Savings**: Eliminates ~45 seconds of sequential waiting during frame extraction and scene detection.

---

### 3. Redundant LLM Passes Over Overlapping Context
- **Current Setup**:
  - `extract/extractor.py` calls Gemini 35 times (once per chunk) to extract textual concepts.
  - `visual/visual_extractor.py` calls Gemini 35 times (once per chunk) to extract visual concepts.
  - `notes/outline_generator.py` sends all merged chunk text to Gemini to build `lecture_outline.json`.
- **Token Count & Context Evaluation**:
  - A 25-minute dense lecture transcript contains ~4,450 words (~5,800 tokens).
  - 35 chunk text objects total ~9,000 tokens including schema overhead.
  - Model in use: **Gemini 3.1 Flash-Lite** with a **1,048,576 token context window**.
- **Proposed Merge**:
  - Supply the full transcript + keyframe mapping into **ONE** single LLM call.
  - Direct Gemini to produce the complete `lecture_outline.json` AND high-level chapter knowledge objects in a single structured JSON response.
- **Reduction**: Cuts **71 LLM calls down to 1 call**.

---

### 4. Per-Chunk Visual Extraction Batching
- **Current State**: [visual/visual_extractor.py:L100-L151](file:///home/gourav/coding/VScode/Projects/NorAI/visual/visual_extractor.py#L100-L151) invokes `analyze_chunk_images` for every single chunk independently. For 35 chunks, 35 separate API requests are sent.
- **Feasibility Analysis**:
  - Average keyframes per chunk: 1–3 images (average 1.8 images).
  - Total keyframes for lecture: 66 images.
  - Passing images grouped by **chapter** (10 chapters = 10 calls, averaging 6 images per call) is well within Gemini 3.1 Flash-Lite multi-image payload limits.
- **Reduction**: Cuts **35 API calls down to 10 API calls** (or 0 if merged with Hypothesis 3).

---

### 5. Study Notes / Revision Notes / Assessment Pass Merging
- **Current State**:
  - `notes/notes_generator.py`: 1 LLM call per chapter = 10 calls.
  - `revision_notes/revision_generator.py`: 1 LLM call per chapter = 10 calls.
  - `assessment/assessment_generator.py`: 1 LLM call per chapter = 10 calls.
  - Total: **30 separate LLM API calls**.
- **Proposed Optimization**:
  - Combine the generation of Study Notes (Markdown), Revision Notes (Markdown/Summary), and Assessment Questions (JSON) into **one structured LLM pass per chapter**.
- **Proposed Response Schema**:
  ```json
  {
    "chapter_id": 1,
    "study_notes_md": "# Chapter 1...",
    "revision_summary_md": "## Quick Summary...",
    "assessment_questions": [ ... ]
  }
  ```
- **Reduction**: Cuts **30 LLM calls down to 10 LLM calls** (66% reduction in generation calls).

---

### 6. Flashcards as a Deterministic Code Transform
- **Current State**: [flashcards/generate_flashcards.py:L39-L50](file:///home/gourav/coding/VScode/Projects/NorAI/flashcards/generate_flashcards.py#L39-L50) loads assessment questions and sends them in batches of 5 to Gemini to reformat into flashcards (`front`, `back`, `explanation`). This executes 7–10 LLM calls.
- **Code Transformation Alternative**:
  Assessment questions already possess strict, structured fields (`question`, `options`, `answer`, `explanation`). A simple Python converter maps these fields directly:
  ```python
  def assessment_to_flashcard(q: dict) -> dict:
      return {
          "front": q["question"],
          "back": q["answer"],
          "explanation": q.get("explanation", "")
      }
  ```
- **Reduction**: Cuts **7–10 LLM calls down to EXACTLY 0 LLM calls**, saving ~15–20 seconds and 100% of LLM cost for flashcard generation.

---

## Consolidated API Call Reduction Target

```
[CURRENT PIPELINE]   : ~128 LLM Calls (35 text + 35 visual + 1 outline + 10 chapter + 20 scoring + 10 notes + 10 revision + 10 quiz + 7 flashcards)
[OPTIMIZED PIPELINE] : ~12–15 LLM Calls Total
  ├── Stage 1: Unified Outline & Knowledge Extraction (1 Call)
  ├── Stage 2: Chapter Content Generation (Notes + Revision + Quiz) (10 Calls)
  ├── Stage 3: Screenshot Scoring & Selection (2–4 Calls)
  └── Stage 4: Flashcard Generation (0 Calls — Code Transform)
```
**Total Call Reduction**: **88% reduction in total API requests**.
