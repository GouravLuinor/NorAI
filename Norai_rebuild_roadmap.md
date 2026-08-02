# NorAI — Rebuild Roadmap

Status: Planning only. No implementation until this roadmap is reviewed and agreed.

Purpose: organize everything surfaced by the overnight audit + follow-up investigation into a sequenced plan, grouped by dependency and readiness — not just a flat list of findings.

---

## Constraint That Shapes Everything Below

**Google AI Studio free tier: 15 RPM / 500 RPD.** This is a hard ceiling, not a soft optimization target. At current pipeline shape (~128 calls for a 25-min lecture), one lecture already consumes ~25% of the daily quota. This constraint raises the priority of API-call reduction work beyond "nice to have cost savings" — it directly determines how many lectures/day the system can realistically process. Keep this in view when sequencing everything else.

---

## Tier 0 — No Dependencies, No Open Questions, Ready to Implement Anytime

These are fully diagnosed, isolated, and carry no design ambiguity. Can be done in any order, independently, whenever convenient.

1. **Delete dead H.264 conversion code** (`ingest/ingest.py`) — `convert_to_h264()` confirmed unused. Pure deletion, zero risk.
2. **Fix chunk-to-screenshot mapping gap** (`visual/mapper.py`) — add nearest-keyframe fallback (within ±20s tolerance) when strict boundary check yields zero screenshots. Root cause fully diagnosed (Chunk 3 case). Zero risk, isolated to one function.
3. **Recalibrate screenshot Pass 1 scoring rubric** (`notes/screenshot_selector.py`) — fix `FRAME_QUALITY_PROMPT` wording so text-heavy slides score appropriately (6-8 range) instead of being systematically under-scored. Threshold (`MIN_CONTENT_DENSITY = 6`) stays as-is; only prompt wording changes. Root cause fully diagnosed (SVM chapter case).
4. **Parallelize frame extraction + scene detection with transcription + chunking** (`backend/orchestrator.py`) — Branch A (transcribe→chunk) and Branch B (frames→scenes) both depend only on Stage 1 output, not each other. Confirmed no shared dependency. Time-savings win, no call-count change, no quality tradeoff.
5. **Fix directory traversal on `lecture_id`** (`backend/main.py`, `backend/dependencies.py`) — sanitize to alphanumeric/UUID pattern. Security fix, isolated, no design decision needed.
6. **Fix unvalidated upload filenames** (`backend/main.py`) — use `Path(file.filename).name`. Same category as above, bundle together.
7. **Fix SSRF risk in URL matching** (`ingest/ingest.py`) — replace substring domain checks with exact `urlparse(url).netloc` whitelist matching.
8. **Add `try/finally` around OpenCV VideoCapture** (`visual/extract_frames.py`) — resource leak fix, isolated.
9. **Switch SQLite connections to context managers** (`backend/main.py`) — resource leak fix, isolated.
10. **Enable SQLite WAL mode + busy_timeout** (`backend/dependencies.py`, `backend/main.py`) — fixes "database is locked" errors under concurrent access. Isolated config change.
11. **Add file locking to `lectures.json` registry writes** (`backend/lecture_registry.py`) — prevents corruption under concurrent pipeline runs.
12. **Consolidate rate limiter into a single shared instance** (currently duplicated across 6 files) — straightforward refactor, no behavior change other than fixing the actual bug (fragmented limiters undercounting real concurrent load).
13. **Remove dead PDF builder modules** (`assessment/assessment_pdf_builder.py`, `notes/study_pdf_builder.py`, `revision_notes/revision_pdf_builder.py`, `backend/generate_pdfs.py`) — confirmed superseded by frontend rendering.
14. **Clean up root-level orphan files** (`test_api.py`, `visual.txt`, `tree.txt`).
15. **Centralize hardcoded config** (model names, frame interval, chunk size, max retries) into a single `config.py` — mechanical refactor, no behavior change, just removes drift risk (e.g. the `tutor/config.py` model-name mismatch we already flagged).

**Note on sequencing within Tier 0**: #12 (rate limiter consolidation) is worth doing *before* any Tier 1 work that changes call patterns, since Tier 1 changes will alter concurrency behavior and you want the rate limiter fixed first so you're not debugging two things at once.

---

## Tier 1 — Needs a Design Decision Before Implementation

These are diagnosed at the "what's wrong" level but need an actual decision on *how* before writing code. Do not implement until each has an explicit answer.

### 1.1 Flashcards → deterministic transform
- **What's known**: Currently a second LLM pass off assessment data, then a *third* compression pass to fit UI size constraints. Both extra passes should be eliminated.
- **What's decided**: Extend assessment generation to output flashcard-ready `flashcard_front`/`flashcard_back` fields in the *same* call as the rest of assessment content — no separate pass at all.
- **Confirmed Word Limits** (from `generate_flashcards.py` prompt & UI constraints):
  - `flashcard_front`: **max 15 words** (short, self-contained question)
  - `flashcard_back`: **max 20 words** (short, precise answer)
  - `flashcard_explanation`: **max 30 words** (brief clarifying explanation)
- **Status**: Ready for implementation. Recommended to implement alongside or right after Tier 1.2 (structured output rollout), embedding these exact field constraints directly into the Pydantic schema for `Question` objects.

### 1.2 Adopt structured output (`responseSchema`) across all LLM calls
- **What's known**: Gemini 3.1 Flash-Lite supports enforced JSON schema output via Pydantic. This was not available under the old Gemma 4 setup and is a genuine unlock now.
- **What it fixes**: malformed JSON failures (confirmed real problem in your progress doc — "Expecting ',' delimiter" errors, retry loops).
- **What it does NOT fix**: call count, blast radius of failures, or content quality — it only guarantees *shape*, not correctness of content.
- **Decision needed**: sequencing — should this be rolled out to *all* existing calls first (as a reliability upgrade, independent of any call-count changes), or done *together with* Tier 2's call consolidation (since merged calls especially need schema enforcement to be trustworthy)? Recommend: do this first, standalone, since it's valuable regardless of what happens with Tier 2.

### 1.3 `MAX_GAP_SECONDS = 90` scene detection tuning
- **What's known**: A 90-second max gap between forced keyframes is roughly one full chunk's duration (chunks average ~57-80s), meaning a chunk can legitimately get zero forced keyframes even with the Tier 0 mapping fallback in place.
- **Open question**: lower this value (e.g. to 45-60s)? Tradeoff is more raw keyframes to filter through downstream (more Pass 1 scoring calls) vs fewer zero-screenshot chunks. Needs a decision on which failure mode is more acceptable, not just a code change.
- **Depends on**: should probably be evaluated *after* Tier 0 fixes #2 and #3 are live and you've seen whether the mapping fallback alone resolves most zero-screenshot cases, before deciding if this tuning is even still needed.

---

## Tier 2 — Architecture-Level, Needs the Pipeline Redesign Sketch First

These are the "collapse call count" ideas from the original audit. Explicitly NOT ready to implement — needs the design sketch (see "Before Tier 2" below) done first, on paper, before any code changes.

### 2.1 Batch visual extraction by chapter instead of per-chunk
- Current: 35 calls (1 per chunk, ~1.8 candidate images avg each)
- Proposed: ~10 calls (1 per chapter, batched images)
- Status: directionally agreed as sensible middle ground (vs the audit's more aggressive "merge into 1 call" idea, which was flagged as too fragile). Not yet designed in detail — retry/failure granularity per chapter batch needs defining.

### 2.2 Merge Knowledge Extraction + Outline Generation
- Current: 35 + 1 = 36 calls
- Audit's proposal: 1 mega-call using full 1M context
- Flagged concern: single point of failure for the entire lecture; malformed JSON in one giant response could lose everything, vs isolated per-chunk retries today.
- Status: rejected as proposed. Needs a middle-ground redesign (e.g. per-chapter or per-segment batching, not per-lecture) — not yet sketched.

### 2.3 Merge Study Notes + Revision Notes + Assessment into one call per chapter
- Current: 30 calls (10 chapters × 3 artifact types)
- Audit's proposal: 10 calls (1 per chapter, all 3 artifacts in one structured response)
- Flagged concern: same fragility issue — one bad chapter response now corrupts three artifact types instead of one.
- Status: plausible but needs explicit decision on acceptable failure handling (e.g., can you retry just the `assessment_questions` field of a chapter's response if only that part is malformed, or does the whole chapter re-generate?).

### 2.4 Sequential Files API upload parallelization/removal
- Current: ~0.65s per image × up to 66 images sequential = up to ~43s overhead on a 25-min lecture
- Proposed: either `ThreadPoolExecutor` parallel uploads (~87% latency reduction) or skip Files API entirely via inline byte embedding (since images are small, ~95KB avg)
- Status: this one is actually closer to Tier 0 in risk (isolated, no schema/call-count implications) — reclassify as a candidate for early implementation once Tier 0 is done, doesn't need to wait for the full pipeline redesign.

---

## Before Tier 2: The Missing Step

None of Tier 2 should be implemented until there's an actual sketch of the target pipeline — not a list of individual call merges, but a diagram of: what runs per-chunk vs per-chapter vs per-lecture, where retry boundaries sit, what happens on partial failure at each level, and how this interacts with the 15 RPM / 500 RPD ceiling at 1.5-2x scale (50-min lecture estimate: ~190-250 calls under current shape).

This should be a whiteboard/diagram exercise using the real data already gathered (chunk sizes, chapter counts, timing breakdown, call breakdown) — not something to hand to an agent as an implementation prompt yet.

---

## Do Not Touch Yet

- **Tutor/LangGraph subsystem** — audit only shallow-checked this; treat as out of scope until the main pipeline work is done and it gets its own dedicated review pass.
- **Multi-user / auth / deployment hardening** (CORS lockdown, endpoint auth) — correctly deferred until there's an actual deployment target; no need to design this speculatively right now.
- **Database modernization (SQLite → Postgres)** — audit suggested this for scale, but nothing in current usage (single user, local) demands it yet. Revisit only if/when multi-user becomes a real near-term goal.
- **Async DAG workflow engine (Temporal/Prefect)** — audit's most speculative suggestion. Way too large a change to consider before the simpler Tier 0/1/2 work is done and you've seen whether that's even sufficient.

---

## Suggested Sequence (Summary)

1. Tier 0, all items — can start immediately, any order, low risk
2. Tier 1.2 (structured output rollout) — do this early since it's a standalone reliability win
3. Tier 1.1 (flashcards) — resolve the open size-constraint question, then implement, likely after 1.2 since the new schema fields benefit from structured output
4. Tier 1.3 (scene detection gap tuning) — revisit after Tier 0 mapping fix is live and observed
5. Tier 2.4 (upload parallelization) — can slot in early, it's low-risk despite being categorized under Tier 2
6. Whiteboard/design session for the rest of Tier 2 — before any of 2.1/2.2/2.3 get implemented
7. Tier 2.1/2.2/2.3 implementation — only after step 6 produces an actual target design
