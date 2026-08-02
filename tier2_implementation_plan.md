# Tier 2 Implementation Plan — Pipeline Consolidation & Latency Optimization

**Target Subsystems**: Ingestion, Visual Extraction, Notes Generation, Assessment, Revision Notes  
**Status**: Approved (Proceeding with Step-by-Step Implementation)

---

## 1. Overview & Strategy

Tier 2 collapses the pipeline's API call footprint from **~121 calls down to ~45 calls** for a standard 25-minute lecture while eliminating **~43 seconds** of sequential network blocking latency.

```
Current Pipeline Call Breakdown (~121 Calls):
- Text Knowledge Extraction  : 40 calls (1 per chunk - isolated for retry resilience)
- Visual Extraction          : 40 calls (1 per chunk)
- Outline Generation         : 1 call
- Screenshot Selection Pass 1: 4 calls (batch size 10)
- Screenshot Selection Pass 2: 9 calls (1 per chapter)
- Study Notes Generation     : 9 calls (1 per chapter)
- Revision Notes Generation  : 9 calls (1 per chapter)
- Assessment Generation      : 9 calls (1 per chapter)
- Flashcards Generation      : 0 calls (deterministic transform)

Target Tier 2 Pipeline Call Breakdown (~45 Calls):
- Text Knowledge Extraction  : 40 calls (1 per chunk - isolated for retry resilience)
- Outline Generation         : 1 call
- Visual Extraction (2.1)    : ~9 calls (1 per chapter batch)
- Screenshot Selection Pass 1: 4 calls (batch size 10)
- Screenshot Selection Pass 2: 9 calls (1 per chapter)
- Merged Artifact Pass (2.3) : 9 calls (1 per chapter: Study Notes + Revision + Assessment + Flashcards)
```

---

## 2. Component Design & Changes (2.0, 2.1, 2.3)

---

### Task 2.0: Files API Parallelization (`visual_extractor.py` & `screenshot_selector.py`)

#### Problem Statement
Currently, `client.files.upload(file=path)` is invoked in a synchronous `for` loop across up to 66 candidate keyframes, causing ~0.65s per file network latency overhead (~43s total cumulative blocking time).

#### Files & Functions to Modify
- **[visual/visual_extractor.py](file:///home/gourav/coding/VScode/Projects/NorAI/visual/visual_extractor.py)**: `process_chunk_images()`
- **[notes/screenshot_selector.py](file:///home/gourav/coding/VScode/Projects/NorAI/notes/screenshot_selector.py)**: `score_frames_batch()`

#### Proposed Change
Replace the synchronous loop with a `ThreadPoolExecutor` async uploader helper:

```python
def upload_files_parallel(client: genai.Client, file_paths: list[str], max_workers: int = 6) -> list:
    """Upload images concurrently to Gemini Files API."""
    def _upload(p):
        return client.files.upload(file=p)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_upload, p) for p in file_paths]
        return [f.result() for f in futures]
```

#### Risk & Behavioral Impact
- **Zero Risk**: No schema changes, no call count changes, no failure mode changes.
- **Latency Win**: Reduces 43 seconds of upload blocking to **~5.5 seconds**.

---

### Task 2.1: Chapter-Batched Visual Knowledge Extraction (`visual_extractor.py`)

#### Problem Statement
Currently, `process_chunk_images()` fires **1 LLM call per chunk** (~40 calls total). Most chunks have 0 or 1 candidate images, making chunk-by-chunk LLM invocation inefficient and quota-heavy.

#### Files & Functions to Modify
- **[visual/visual_extractor.py](file:///home/gourav/coding/VScode/Projects/NorAI/visual/visual_extractor.py)**: Replace `process_chunk_images()` and `analyze_all_chunks()` with `process_chapter_visual_batch()` and `analyze_all_chapters()`.
- **[extract/merger.py](file:///home/gourav/coding/VScode/Projects/NorAI/extract/merger.py)**: Update `merge_knowledge_and_visual()` to accept chapter-level visual outputs.
- **[backend/orchestrator.py](file:///home/gourav/coding/VScode/Projects/NorAI/backend/orchestrator.py)**: Update `_run_visual_branch()` to run chapter-level visual batching.

#### New Pydantic Structured Output Schemas

```python
class VisualObjectItem(BaseModel):
    chunk_id: int
    visual_notes: str
    important_information: list[str]
    ocr_text: str
    visual_summary: str
    visual_type: str
    teaching_stage: str
    importance_score: int
    include_in_notes: bool
    source_screenshots: list[str]


class ChapterVisualKnowledgeModel(BaseModel):
    chapter_id: int
    incomplete: bool = Field(
        default=False, 
        description="Set to true if visual processing was partially degraded"
    )
    visual_objects: list[VisualObjectItem]
```

#### Failure Handling & Graceful Degradation (`incomplete: true`)
- If a chapter's visual batch call fails after 3 retries:
  - The chapter's visual output degrades gracefully to empty visual objects (`visual_objects: []`, `incomplete: true`).
  - Pipeline execution **does NOT halt**. Chunks within that chapter fall back to `merge_objects_without_visual()`.
  - The output JSON file `chapter_visual_{chapter_id}.json` stores `"incomplete": true`.

---

### Task 2.3: Merged Chapter Artifact Generation (`notes_generator.py`, `assessment_generator.py`, `revision_generator.py`)

#### Problem Statement
Currently, each chapter triggers **3 separate LLM calls**:
1. `generate_chapter_notes()`
2. `generate_revision_notes()`
3. `generate_chapter_questions()`
For 10 chapters, this requires **30 LLM calls**.

#### Files & Functions to Modify
- **[notes/notes_generator.py](file:///home/gourav/coding/VScode/Projects/NorAI/notes/notes_generator.py)**: Create unified `generate_chapter_artifacts()` function returning all 3 artifact types + flashcards in 1 call.
- **[assessment/assessment_generator.py](file:///home/gourav/coding/VScode/Projects/NorAI/assessment/assessment_generator.py)**: Re-export question schemas and helper models used by the unified generator.
- **[revision_notes/revision_generator.py](file:///home/gourav/coding/VScode/Projects/NorAI/revision_notes/revision_generator.py)**: Add `render_revision_markdown()` helper to bridge structured outputs into standard Markdown format expected by frontend & PDF pipelines.
- **[flashcards/generate_flashcards.py](file:///home/gourav/coding/VScode/Projects/NorAI/flashcards/generate_flashcards.py)**: Execute 0-call transformation from the merged output.

#### New Pydantic Structured Output Schemas

```python
class CoreConceptItem(BaseModel):
    concept: str
    explanation: str


class MergedChapterArtifactsModel(BaseModel):
    chapter_id: int
    incomplete: bool = Field(
        default=False,
        description="Set to true if any artifact section failed to generate fully"
    )
    
    # 1. Study Notes Artifact
    study_notes_markdown: str = Field(
        description="Comprehensive, highly detailed Markdown study notes for this chapter with headings, bullet points, latex math, and screenshot embeds."
    )
    
    # 2. Revision Notes Artifact
    revision_summary: list[str] = Field(
        description="3 to 5 core bullet points summarizing the key exam takeaways for this chapter."
    )
    core_concepts_breakdown: list[CoreConceptItem] = Field(
        description="List of key concepts with brief 1-2 sentence quick-ref explanations."
    )
    
    # 3. Assessment Artifact (Includes Flashcard fields directly)
    assessment_questions: list[Question] = Field(
        description="Chapter quiz questions (MCQ, True/False, Short Answer) with embedded flashcard_front/back/explanation fields."
    )
```

#### Revision Markdown Rendering Bridge (`render_revision_markdown()`)
To ensure `revision_chapter_{chapter_id}.md` retains the exact Markdown structure expected by the frontend and PDF builder pipelines, a deterministic renderer function `render_revision_markdown()` is added to `revision_notes/revision_generator.py`:

```python
def render_revision_markdown(
    chapter_id: int,
    chapter_title: str,
    revision_summary: list[str],
    core_concepts_breakdown: list[CoreConceptItem],
) -> str:
    """Bridge structured JSON revision outputs into standard Markdown format."""
    lines = [
        f"# Revision Notes — Chapter {chapter_id}: {chapter_title}\n",
        "## Key Exam Takeaways\n",
    ]
    for bullet in revision_summary:
        lines.append(f"- {bullet}")
    
    lines.append("\n## Core Concepts Breakdown\n")
    for item in core_concepts_breakdown:
        lines.append(f"- **{item.concept}**: {item.explanation}")
        
    return "\n".join(lines)
```

#### Failure Handling & Downstream File Output Preservation
- Although generated in a single consolidated LLM call, `generate_chapter_artifacts()` writes individual backward-compatible files:
  - `outputs/{lecture_id}/notes/chapter_{chapter_id}.md`
  - `outputs/{lecture_id}/revision/revision_chapter_{chapter_id}.md`
  - `outputs/{lecture_id}/assessment/assessment_chapter_{chapter_id}.json`
  - `outputs/{lecture_id}/flashcards/flashcards_chapter_{chapter_id}.json`
- **Downstream Consumer Zero-Impact Guarantee**:
  - The frontend, backend API routes (`GET /notes`, `GET /assessment`, `GET /flashcards`), and Tutor vector indexing (`build_index.py`) **read these exact file paths**.
  - Writing backward-compatible files ensures 0 changes are required in frontend stores (`useThreadStore.ts`) or Tutor retriever code!

---

## 3. Implementation Order & Complexity Estimates

| Order | Task | Scope / Complexity | Estimated Development Time | Latency / Call Savings |
|---|---|---|---|---|
| **Phase 1** | **Task 2.0**: Files API Parallelization | Low (Isolated helper functions) | 30 minutes | Saves **~38 seconds** wall-clock time |
| **Phase 2** | **Task 2.1**: Chapter Visual Batching | Medium (Visual extractor + Merger update) | 1.5 hours | Saves **~31 LLM calls** |
| **Phase 3** | **Task 2.3**: Merged Chapter Artifacts | Medium-High (Unified prompt + Pydantic model + Markdown Renderer) | 2 hours | Saves **~20 LLM calls** |

---

## 4. Open Questions & Technical Risks for Review

> [!IMPORTANT]
> **Open Question 1: Gemini 3.1 Flash-Lite Markdown Output Quality in Enforced Schema**
> In Task 2.3, `study_notes_markdown` is requested inside a Pydantic `response_schema` alongside `assessment_questions`.
> - *Risk*: Enforcing JSON output structure on a large string field (`study_notes_markdown`) can occasionally cause LLM output truncation if response max tokens ceiling is reached.
> - *Mitigation*: We set `max_output_tokens=8192` in `GenerateContentConfig`.

> [!WARNING]
> **Open Question 2: Partial Degradation Flag (`incomplete: true`) Surface in Frontend**
> Should the frontend display a subtle visual indicator (e.g. warning badge: *"Partial content generated"*) when `incomplete: true` is present on a chapter JSON?
> - *Recommendation*: Currently, silent degradation allows the UI to render whatever content succeeded. Adding `"incomplete": true` to the JSON schema allows the UI to optionally surface a warning toast without breaking rendering.
