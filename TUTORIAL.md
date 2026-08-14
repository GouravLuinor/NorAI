# NorAI — Full-Project Tutorial & Interview Prep

Everything built in this project — from the 18-stage pipeline and RAG tutor to
the Supabase auth and PDF exports — the concepts behind it, what you should know
as a developer, and the questions interviewers are likely to ask, with full
answers.

The project is ordered **oldest → newest**, matching the git history. The table
below shows the recent milestone commits (later milestones get full parts; the
earliest skeleton/mock-data commits are folded into the architecture parts).

| Commit | What it did |
|---|---|---|
| `1805f00` → `…` | Initial skeleton → multi-source ingestion → chunking → RAG → pipeline (Parts 1–2) |
| `5715261` → `3ff9fa4` | Frontend shell, real backend integration, workspace, design-token overhauls (Part 3) |
| `7234c00` | Mind-map (Phase D) concept map, floatable cards & tutor source/reference fixes |
| `5175684` | Production Micro-SaaS foundation — DB schema, auth, webhooks & landing/pricing UI (Part 4) |
| `a12a387` | QA fixes — tutor memory, missed-question correctness, quiz load path & flashcard stats |
| `dacad59` | Wire Supabase end-to-end — Postgres + real auth (Part 5) |
| `e67918b` | Real guide & mind-map PDFs, interactive HTML export, continuous-flow print (Part 6) |
| `f46b949` | Landing/pricing review pass — type-scale tokens, a11y, mobile overflow & copy (Part 7) |
| `0a8bfe6` | **P0** security hardening — webhook fail-closed, static allowlist, SSRF/upload gates, error sanitization |
| `bddaa9b` / `9e0dccb` | **P1** pipeline economics — chunk drift fix, batched/diff-synced indexing, hash-of-inputs caching, adaptive chunking, cost estimate |
| `eb7614d` | **P2** billing & quota — usage metering, pre-spend enforcement, quota badge, billing page |
| `6c10b7f` | **P3** tutor retrieval hardening — golden-QA evals, hybrid BM25+RRF, verified citations, cross-turn chapter state |
| `878e383` / `f3c8e0b` | **P4** job durability — DB-backed job queue, GC, Alembic migrations, async tutor persistence, SSE scaffolding removed |
| `fa845c5` | **P5.1–5.3** observability (structured logging), dep hygiene, CI |
| `9a9a3db` | **P5.4** single-container Docker image (SPA served by FastAPI) |
| `93dea03` | **P5.5–5.6** typed API client, strict TS, route code-splitting & resilience |
| `2930a52` | **P5.8** frontend tests (Vitest) + offline API contract tests |
| `52c5a68` / `ef55011` | **P6.1** real token streaming — `astream_events(v2)` on `/chat/stream` |
| `167c17f` / `c02e83c` | **P6.2** SM-2 spaced repetition + Anki `.apkg` export |
| `2ee1613` | **P6.3** click-to-video grounding — YouTube seek-map player + timestamp persistence fixes |
| `5760bc3` | **P6.5** per-stage Gemini usage/cost dashboard |
| `fa01920` / `dc68924` | **P7** token reduction — prompt compression + context caching + output-token cut |
| `8c4cd74` | **P6.4 + UI/UX audit execution** — course collections + share links, and the Architect's Sketchbook v2 redesign (3 responsive tiers, skeletons, custom Select, dark-theme fixes) |

**What you learned in one paragraph:** you built an end-to-end AI platform that
turns lecture videos into structured study material. An **18-stage multimodal
pipeline** (Faster-Whisper transcription + Gemini knowledge extraction + OpenCV
visual analysis) runs in a background thread inside a **DB-backed job queue** and
persists progress to the database; a **LangGraph + ChromaDB RAG tutor** with
hybrid (dense+BM25) retrieval and verified citations retrieves lecture-grounded
context and answers conversationally — with **real token streaming** over SSE; a
**React workspace** with notes/revision/assessment/flashcards/mind-map panels
polls progress and streams tutor answers; then you **productionized** it with
Postgres, real Supabase auth (JWT verified via JWKS), usage metering and Lemon
Squeezy webhooks; hardened **PDF exports** via the browser print pipeline; and
finally shipped a **P0→P7 hardening pass**: security gates, pipeline cost cuts,
billing/quota, retrieval evals, a restart-survivable job queue, Docker, a test
suite, **retention features** (SM-2 spaced repetition, Anki export, click-to-video
grounding, course collections + share links, usage/cost dashboard), a **token-reduction
sprint** (prompt compression, dormant context caching, output-token cut), and a
frontend **UI/UX audit execution** (3 responsive tiers, skeletons, custom Select).

---

# Part 1 — The 18-Stage Pipeline

## 1.1 Big picture: video in → knowledge out

The pipeline is the heart of NorAI. A single lecture video goes through
transcription, knowledge extraction, visual analysis, merging, and dynamic
chapter structuring to produce notes, revision material, assessments, flashcards,
and searchable indexes.

```
Lecture Video
  ↓
Text branch (transcript)      Visual branch (frames)
  ↓                            ↓
  transcribe ──────────────►   extract frames
  chunk ────────────────────►  scene detect
  extract knowledge ────────►  └──► map chunks↔screenshots
        └───────────┬─────────────┘
                    ↓
   outline (dynamic chapters) → visual understanding → merge
                    ↓
   chapters → study notes + revision + assessment + flashcards
                    ↓
   tutor index (notes) + screenshot index (ChromaDB)
```

## 1.2 The execution model (understand this cold)

`backend/orchestrator.py` is **fully synchronous** and runs inside a worker
thread owned by a **DB-backed job queue** (`backend/jobs.py`). `POST /process`
no longer spawns a raw thread — it **enqueues a `Lecture` row** with
`status="queued"`, and a **supervisor thread** (started once at app startup)
polls the DB, claims jobs within global + per-user concurrency caps, and runs
each one in a bounded `ThreadPoolExecutor`. Why a worker thread and not asyncio?

- The pipeline makes long blocking calls (FFmpeg, Faster-Whisper, Gemini HTTP)
  that would stall an async event loop.
- The DB-backed queue gives you **durability**: jobs survive a server restart,
  and a job whose heartbeat goes stale is re-queued and resumed (P4.1).

The lifecycle on the `lectures` row:

```
queued → processing → completed
                   |→ queued (transient failure, attempts left)
                   |→ cancelled (user cancelled mid-run)
                   |→ failed (retries exhausted, ≤ PIPELINE_MAX_ATTEMPTS)
```

The **supervisor loop** (`backend/jobs.py`) does three things every poll
interval: recover `processing` jobs with stale heartbeats (re-queue or fail),
claim `queued` jobs that fit the caps, and (once a day) run GC to purge stale
uploads and DB-orphaned lecture dirs. Because every pipeline stage is
**cache-first** (P1.4, hash-of-inputs), a recovered job re-runs at **~0 Gemini
calls** — crash recovery is effectively a cheap resume.

Inside the worker thread, the two independent branches run **in parallel** with
a `ThreadPoolExecutor(max_workers=2)`:

```python
def _run_text_branch():    # transcription → chunking → knowledge extraction
def _run_visual_branch():  # frame extraction → scene detection
```

Both branches' `.result()` are awaited before the sequential stages that follow.
This halves wall-clock time for the two expensive, independent parts.

> **Single-process assumption:** the supervisor is deliberately single-worker.
> Multiple uvicorn workers would each start a supervisor; a DB claim-lock would
> be needed before running `--workers > 1`.

## 1.3 Progress tracking: DB-persisted, polled (no SSE)

Progress lives on the **`lectures` DB row** — `stage`, `stage_message`,
`progress`, `heartbeat_at`. The worker calls `on_progress(stage, message,
percent)`, which persists the fields:

```python
def update_job_progress(lecture_id, stage, message, percent):
    # reads the Lecture row, sets stage/message/progress, refreshes heartbeat_at
    # `stage=None` is a heartbeat-only refresh — long stages must not look stuck
```

`GET /process/{id}/status` is **DB-backed** and maps the lifecycle onto the
legacy `{stage, message, progress}` poll contract (`completed → "complete"`,
`failed/cancelled → "error"`, else the live stage), so the frontend poller is
unchanged. A separate `POST /process/{id}/cancel` sets `cancel_requested`, which
the worker checks between stages and turns into `PipelineCancelled`.

> **Gotcha worth knowing for interviews:** the old SSE push scaffolding
> (`_queues` / `asyncio.run_coroutine_threadsafe` against a never-started event
> loop) was **removed** in P4.5 — progress is polling-only. The *only* true SSE
> stream in the app is `POST /chat/stream` (Part 2.10).

## 1.4 Stage-by-stage (the actual order in the code)

| # | Progress stage | What happens | Engine |
|---|---|---|---|
| 1 | `ingestion` | `process_source` routes YouTube (`yt-dlp`) / Google Drive (`gdown`) / upload; extracts MP3 via FFmpeg; writes `videos/`, `audio/`, `metadata/` | Local tools |
| 2–4 | `transcription` → `chunking` → `knowledge_extraction` | **Faster-Whisper** → timestamped `transcripts/*.json`; groups ~15 transcript segments (adaptive) into chunks; per-chunk **Gemini** structured `KnowledgeObject` with retries + rate limiter | Local + Gemini |
| 5–6 | `frame_extraction` → `scene_detection` | samples frames every 8s via OpenCV → pixel-diff threshold dedup → keyframes (runs in parallel with 2–4) | Local |
| 7 | `mapping` | associates keyframes to transcript chunks by timestamp → `mappings/chunk_screenshot_mapping.json` | Local |
| 8 | `outline` | LLM infers title + 3–6 chapters, renumbers `chapter_id`s, assigns chunk ranges | Gemini |
| 9 | `visual_knowledge` | **Gemini multimodal** reads chapter-batched keyframe images → `visual_objects/` | Gemini |
| 10 | `knowledge_merging` | fuses text + visual objects → `merged_objects/` | Local |
| 11 | `chapter_building` | aggregates merged objects into Pydantic `Chapter`s (no LLM) → `chapters/chapter_N.json` | Local |
| 12 | `screenshot_selection` | two-pass: quality scoring (Gemini) → perceptual-hash dedup → top-K ranking → `screenshots/selected/` | Gemini + local |
| 13–16 | `chapter_artifacts` | **one Gemini call per chapter** → study notes + revision + assessment + flashcards (`MergedChapterArtifactsModel`) — stages 13–16 are a single consolidated call | Gemini |
| 17 | `tutor_index` | chunks `notes/chapter_*.md`, diff-syncs embeds into per-lecture Chroma `norai_notes` (content-hashed ids) | Chroma + Gemini embed |
| 18 | `screenshot_index` | indexes screenshot captions into `screenshot_captions` collection (diff-sync) | Chroma + Gemini embed |
| — | `cleanup` | deletes transient dirs (videos/audio/raw/chunks/mappings/metadata) on success, failure, or cancel | Local |

## 1.5 Design principle: partial failure tolerance

Nearly every stage from `mapping` onward is wrapped in:

```python
try:
    ...
except Exception as e:
    logger.error(f"X failed (continuing): {e}")
```

**A failed optional stage never destroys the whole run.** Only ingestion, the
duration check, and the two parallel branches hard-fail. If outline generation
itself fails, a hardcoded single-chapter fallback outline is written so the
pipeline can continue. This "design for partial failure" is one of the stated
project principles and a great interview answer.

## 1.6 The free-trial duration gate

After ingestion, the pipeline reads `duration` from the metadata JSON and raises
if it exceeds `MAX_FREE_DURATION_MIN` (default 15) while
`ENFORCE_FREE_TRIAL_DURATION=true`:

```python
if duration_sec > max_duration_sec and os.environ.get("ENFORCE_FREE_TRIAL_DURATION", "true").lower() == "true":
    raise ValueError("Lecture duration ... exceeds the Free Trial limit ...")
```

This is how a free user is prevented from processing long lectures — the
monetization story (Part 4). Since P2, there's a **second, earlier gate at the
API layer** (Part 4.3): `POST /process` checks quota *before* any download or
Gemini spend (401 without auth, 429 when `used >= quota` or `used + needed >
quota`).

## 1.7 Lecture isolation & the registry

`backend/lecture_registry.py` maintains a file-backed JSON registry
(`outputs/lectures.json`) guarded by a `threading.Lock`. `create_lecture`
creates `outputs/{lecture_id}/` with subdirs (`notes/`, `revision/`,
`assessment/`, `screenshots/keyframes/`, `screenshots/selected/`, `flashcards/`,
`pdfs/`, `tutor/`). Every stage writes under this dir, so **artifacts never leak
across lectures**. The `lecture_id` (the `task_id`) is the single identity key
propagated through routes, stores, indexes, and conversations.

Since P4.1 the **DB `lectures` row is the source of truth for lifecycle** —
`status`, `stage`, `progress`, `attempts`, `heartbeat_at`, `cancel_requested`,
`source_type`, `source_url`, `duration_seconds`. The filesystem registry still
maps id → output dir, and `GET /lectures` merges both. A daily GC sweep (P4.2)
removes DB-orphaned lecture dirs and stale uploads.

## 1.8 Knowledge extraction (Stage 4) & merging (Stage 10)

- `extract/` sends each chunk to Gemini and gets a structured `KnowledgeObject`
  via Pydantic validation — this is **structured output**: the LLM is forced
  into a schema, and malformed JSON is retried.
- `visual/visual_extractor.py` sends chapter-batched keyframes to Gemini's
  **Files API** (multimodal) and produces per-chapter visual knowledge.
- `extract/merger.py` fuses the text and visual objects into a unified
  `merged_objects/chunk_N.json`. This is "knowledge fusion" — a lecture is
  treated as speech **+** visuals, not just a transcript.

## 1.9 Dynamic outline (Stage 8) — no fixed chapter count

`notes/outline_generator.py` builds "proto chapters" from merged chunks, asks
Gemini for 3–6 chapters, **caps the count** to `max(3, min(8, total_chunks // 3))`,
renumbers `chapter_id` 1…N, and assigns `start_chunk`/`end_chunk`/`chunk_ids`.
Different lectures get different structures — the app never assumes a fixed
number of chapters.

## 1.10 Consolidated chapter artifacts (Stage 13) — the cost saver

This is the current "live" path (`notes/notes_generator.py` →
`generate_consolidated_chapter_artifacts`). For **each chapter** it makes
**one** Gemini call with `response_schema=MergedChapterArtifactsModel` that
returns:

- `study_notes_sections` (typed: definition | callout | table | list | code | prose)
- `revision_summary` + `core_concepts_breakdown`
- `assessment_questions` (with embedded flashcard fields)

Then it writes 4 files: `notes/chapter_N.md` + `chapter_N.json`,
`revision/revision_chapter_N.md`, `assessment/assessment_chapter_N.json`, and
`flashcards/flashcards_chapter_N.json`. On repeated failure it writes degraded
fallbacks flagged `incomplete: true`.

> Interview takeaway: consolidating four artifact types into **one LLM call per
> chapter** is a deliberate cost optimization — instead of 4+ paid calls per
> chapter, you get 1. The older `generate_study_notes` / `generate_revision_notes_*`
> paths are legacy/standalone.

## 1.11 Screenshot selection (Stage 12) — quality + dedup

Two passes per chapter:

1. **Pass 1 quality scoring** in batches of 10 — Gemini scores each frame
   (`content_density`, `instructor_occlusion`, `is_transition_or_decorative`);
   then **perceptual-hash dedup** (`imagehash.phash`, dropping pairs within a
   Hamming distance ≤ 6, keeping the highest-density survivor) removes
   near-duplicate frames.
2. **Pass 2 ranking** — Gemini ranks survivors, then a **deterministic top-K cut**
   in code (`compute_target_count()` → 3/4/5/6 based on candidate count) sets the
   final selection.

## 1.12 Assessment & flashcards: 0 extra LLM calls

- `assessment/` generates questions **inside** the consolidated artifacts call;
  the schema is a flat `Question` with `question_id, chapter_id, type,
  difficulty, concepts, question, options, answer, explanation` + embedded
  `flashcard_front/back/explanation`. Pydantic validators enforce rules like
  "options ≥ 2 only for MCQ/True-False" and "answer ∈ options".
- `flashcards/generate_flashcards.py` is a **deterministic 0-LLM-call transform**:
  it just extracts `flashcard_front/back/explanation` from each question,
  truncating to 15/20/30 words. No model call for cards.

## 1.13 Pipeline economics (P1) — make re-runs free

A cluster of P1 changes cut a full lecture from ~128 LLM calls to ~35, and a
re-run of the *same* lecture id to **0 paid calls**:

- **P1.1 chunk-size drift fixed** — `chunking/chunk.py` imports
  `config.DEFAULT_SEGMENTS_PER_CHUNK` (15) instead of a hardcoded 5, so
  knowledge-extraction calls drop ~3×. Chunking is now **adaptive**
  (`adaptive_segments_per_chunk`).
- **P1.4 hash-of-inputs caching** — `cache_util.py` (`digest` /
  `outputs_current` / `write_marker`, `.sha256` marker sidecars). Whole-stage
  markers + per-chunk digests mean an unchanged input is skipped entirely. Wired
  into extraction, per-chapter notes, outline, visual extraction, and screenshot
  selection.
- **P1.2 batched/diff-synced indexing** — `tutor/build_index.py:upsert_batched`
  (batch 20 + pacing). Stage 17/18 use **content-hashed ids** and diff-sync
  against the per-lecture Chroma (`to_add`/`to_remove`), so identical re-runs
  are no-ops instead of one embed call per doc.
- **P1.3 duplicate multimodal analysis removed** — `screenshot_selector` loads
  the persisted per-chapter visual analysis and synthesizes Pass-1 quality
  scores instead of re-uploading + re-scoring the same keyframes.
- **P1.7 transcription upgrade** — default whisper model `base` → `small` (env
  override `NORAI_WHISPER_MODEL`), with a per-size `_MODEL_CACHE`.
- **P1.8 self-calibrating cost estimate** — `backend/estimator.py` calibrates
  tokens/min from real `UsageLog`/metrics data; `POST /estimate` returns an
  up-front cost + call count before you pay anything, and the orchestrator
  records what actually happened for the next calibration.
- **P1.5 dead-code purge** — `retrieval/`, `vectordb/`, old chapter
  structurer/clusterer and generator modules deleted.

This is why the P4 job queue can offer **free crash recovery**: re-running a
stalled pipeline is ~0 Gemini calls because every paid stage is cache-first.

---

# Part 2 — The RAG Tutor

## 2.1 Big picture

The tutor is a **retrieval-augmented generation (RAG)** system: for each user
question it retrieves relevant note chunks **and** screenshots from
lecture-scoped ChromaDB indexes, injects them as context into a Gemini prompt,
and streams the grounded answer back.

```
User question
  ↓
detect_chapter → rewrite_query
  ↓
retrieve (notes index) + retrieve_images (screenshot index)
  ↓
generate_answer (Gemini + context blocks)
  ↓
save_memory (summarize if >12 msgs)
```

## 2.2 LangGraph state graph

`tutor/graph.py` builds a `StateGraph(ChatState)` with edges:

```
START → load_memory → detect_chapter
   └─(conditional)→ execute_command | quiz_* | start_normal
start_normal → rewrite_query → retrieve + retrieve_images → generate_answer → verify_citations → save_memory → END
```

LangGraph gives you a **stateful, persistent graph**: nodes are functions that
mutate `state`, and the `add_messages` reducer appends to the conversation list.
The compiled graph is bound to a **checkpointer** so conversation state survives
across turns and process restarts. Since P4.4 the checkpointer is an
**`AsyncSqliteSaver`** (`tutor/memory.py:get_async_checkpointer`, WAL +
busy_timeout) and the LLM-touching nodes are `async` — `generate_answer_node`,
`save_memory_node`, `rewrite_query_node`, `quiz_llm_evaluate` all `await
llm.ainvoke(...)`. Tutor turns no longer block the event loop; `ainvoke_tutor`
(`backend/dependencies.py`) serializes per lecture with an `asyncio.Lock` and
caches graphs in an LRU bounded at `TUTOR_MAX_CACHED_GRAPHS` (32, connections
closed on eviction).

## 2.3 Two retrieval indexes, hybrid search

ChromaDB per-lecture, two collections:

| Collection | Contents | Metadata |
|---|---|---|
| `norai_notes` | heading-tree chunks of `notes/chapter_*.md` | `heading`, `heading_path`, `chapter_id`, `source` |
| `screenshot_captions` | screenshot reason/caption strings | `path`, `section`, `importance`, `chapter_id` |

`tutor/retriever.py` exposes `retrieve(query, chapter_id, k)` and
`retrieve_images(...)`. Query results are **filtered by `chapter_id`** via
Chroma's `where={"chapter_id": {"$eq": n}}`, so the tutor stays grounded in the
active chapter. Results include `distance` (cosine); images sort by
`(distance asc, importance desc)`.

Since P3 the notes retriever is **hybrid**: a BM25 sparse index
(`tutor/bm25.py`, lazy-built) is fused with the dense Chroma cosine scores via
**Reciprocal Rank Fusion** (`retriever.py`, 60/40 dense/sparse weight). Lexical
matching catches exact terms embeddings miss. `retrieve()` also does **context
expansion** (`tutor/context_expand.py`) — when a leaf chunk hits, its parent
section + sibling chunks are pulled too.

Clients are **module-level singletons cached with `@lru_cache`** keyed by
`chroma_dir` — this avoids re-creating the Chroma client (and its Rust
underpinnings) on every request, and sidesteps a known Chroma 1.x multi-client
bug. If an index doesn't exist, a clear `IndexNotBuiltError` is raised instead of
a cryptic Chroma exception.

## 2.4 The custom embedding function (a real gemini gotcha)

`tutor/embedding.py` implements `GeminiEmbeddingFunction` for Chroma. Why custom?
The built-in Chroma wrapper only documents `gemini-embedding-001` and passes a
`task_type=` parameter — but **`gemini-embedding-2` dropped `task_type`
entirely**; task instructions belong in the prompt text:

```
Documents:  "title: {title} | text: {content}"
Queries:    "task: question answering | query: {q}"
```

This is **asymmetric embedding**: documents and queries are formatted differently
before embedding, which measurably improves retrieval quality. The class also
wraps each string in its own `Content` object (so each gets a separate
embedding) and retries with **exponential backoff** (2s, 4s, 8s).

## 2.5 Prompt engineering: the CONTEXT block

`generate_answer_node` builds the prompt as separate `SystemMessage`s:

```
[SystemMessage] tutor system prompt (+ lecture title, study mode, persona)
[SystemMessage] CONTEXT block       (retrieved note chunks)
[SystemMessage] IMAGE CONTEXT block (retrieved screenshots)
[HumanMessage/AIMessage] conversation history (windowed)
[HumanMessage] current user question
```

Separate system messages mean the ephemeral per-turn context is visually
distinct in logs and won't be accidentally summarized away. There's also a
**low-confidence mode**: if *all* retrieved chunks exceed `CONFIDENCE_THRESHOLD`
(0.35 cosine distance), the context block header tells the model to express
appropriate uncertainty.

## 2.6 Memory: windowing + incremental summarization

This was a real bug fixed in `a12a387` (the tutor was effectively stateless).
Now:

- **`load_memory_node`** rebuilds `context_messages` every turn from the
  persisted transcript: the **most recent summary** SystemMessage + the **last 6**
  Human/AI messages. This is the "prompt window."
- **`save_memory_node`** fires when **12+ new turns** have accumulated since the
  last summary record; it LLM-summarizes all but the most recent 6 into a
  `CONVERSATION SUMMARY:` SystemMessage appended to the transcript. Since P3.6
  it returns **`RemoveMessage`s** for the summarised turns (the *checkpoint
  store* stays bounded, not just the prompt window) and a `_recent_window`
  char-budget (8000) bounds the retained window.

So the model gets real long-horizon memory without an unbounded prompt.

## 2.7 Query rewriting & chapter detection

- `detect_chapter_node` regex-matches the question for chapter numbers and
  command keywords (`quiz`, `summary`, `flashcards`). Since P3.5 it also writes
  `last_chapter_id` into state — anaphoric follow-ups ("what about that?",
  "why is this?") re-scope retrieval to the remembered chapter, while fresh
  questions search the whole index.
- `rewrite_query_node` has Gemini rewrite the raw question into a
  **self-contained search query** (useful for follow-ups like "what about the
  second one?"). It also resets `retrieved_chunks`/`retrieved_images` so a stale
  retrieval can't leak into a later turn.
- `commands.py` `execute_command` is a **no-LLM tool runner** that starts a quiz
  or shows a summary/flashcards when a command intent is detected.

## 2.8 Verified citations (P3) & low-context statuses (P3.7)

- **`verify_citations_node`** (`tutor/citations.py`) runs **after**
  `generate_answer`: it deterministically post-checks the answer's Sources
  against the retrieved chunk ids — no LLM. The stream and thread-snapshot
  responses surface `verified_citations`; the frontend renders **only** verified
  citations in the references panel (unverified ones are dropped, except when
  retrieval was empty and a `rawText` fallback is shown).
- **Retrieval statuses** — `retrieve_node` sets `retrieval_status` =
  `"ok" | "empty" | "error"` and tags each chunk `confidence_tag` = strong/weak
  vs `CONFIDENCE_THRESHOLD` (0.35). `prompts.py` has distinct
  `_RETRIEVAL_ERROR_NOTE` / low-confidence context-block headers so the model
  expresses uncertainty instead of hallucinating.
- **Golden-QA evals** — `tutor/evals/` (`golden_sets.py`, `runner.py`) measures
  MRR / hit-rate per lecture, and `tutor/test_evals.py` gates regressions.

## 2.9 Quiz-in-chat

`quiz_nodes.py` adds a self-contained quiz loop to the graph: `quiz_ask` →
`quiz_store_answer` → (repeat) → `quiz_llm_evaluate`, which parses a
`FINAL SCORE: X out of Y` line. So a user can take a 5-question quiz inside the
chat with the same conversation context.

## 2.10 `/chat/stream` — SSE streaming (the real SSE in this app)

> **P6.1 (commit `52c5a68` / `ef55011`):** the endpoint now does **true token
> streaming**. Before P6.1 the whole answer was computed up-front and replayed
> in fake 24-char chunks; that fake version is what older copies of this tutorial
> describe. The live code (and this section) is the P6.1+ version.

`POST /chat/stream` (`backend/main.py`):

1. The LangGraph graph is driven with **`graph.astream_events(version="v2")`**
   inside `asyncio.to_thread`. `astream_events` yields real intermediate events,
   so we can emit tokens as the model generates them.
2. We filter the event stream to **`on_chat_model_stream`** events whose
   `metadata["langgraph_node"] == "generate_answer"` — i.e. the streaming tokens
   of the actual answer node, not tool calls or the planner. Each event's
   `event["data"]["chunk"]` is the token text, forwarded as
   `data: {"t": "...", "frame": N}\n\n`.
3. The answer node must call **`llm.astream(...)`** (streaming mode) for these
   events to fire — this is the contract between `tutor/nodes.py` and the
   endpoint.
4. The cache path is handled before streaming: if the question/thread has a
   cached answer (P7 "context caching" / history dedupe), the **whole cached
   answer replays as one frame** with `"final": true`, so the UI is consistent.
5. If no token events were captured at all, we fall back to sending the full
   final answer as a single `{"t": ...}` frame so the user still gets a reply.
6. Final frame `data: {"final": {...}}` carries `assistant_message_id`,
   `retrieved_chunks`, `retrieved_images`, `chapter_id`, `thread_id`; then
   `data: [DONE]`. The `frame` counter + final-answer check lets the frontend
   skip the replay-once-has-answer dedupe.

Headers: `media_type="text/event-stream"`, `Cache-Control: no-cache`,
`X-Accel-Buffering: no`.

On the frontend, `sendChatMessageStream` in `lib/chatApi.ts` is an **async
generator**: it reads `res.body.getReader()` + `TextDecoder`, buffers `\n`
frames, skips non-`data:` lines, and yields string chunks or a `{type:'final'}`
object. The client keeps the frame counter, and if it already received the full
answer as a single replay frame it won't re-render duplicate text. This is a
great example of client-side SSE parsing without `EventSource` (which can't POST
or send auth headers easily).

## 2.11 Threads: two storage layers

- `POST /threads` writes only to the app-owned `user_threads` table (labels,
  metadata).
- `GET /threads/{id}` reads the **LangGraph checkpoint** (the actual message
  history), filters out `SystemMessage`s (so summaries don't leak as bubbles),
  and strips the "Sources" appendix from assistant replies.
- `DELETE /threads/{id}` deletes across `checkpoints`, `checkpoint_blobs`,
  `checkpoint_writes`, and `user_threads`.

---

# Part 3 — The Frontend Workspace

## 3.1 Tech stack & routing

React 19 + TypeScript (strict) + Vite + Tailwind 4 + Zustand 5 + React Router 7 +
framer-motion + react-markdown/KaTeX. Since P5.6 every page is **lazy-loaded**
(`React.lazy` + `<Suspense>`) so each route ships in its own chunk — the entry
bundle dropped from ~1,354 kB to ~364 kB and the marketing routes never download
the markdown/KaTeX/highlight stack (that lives in the shared workspace chunk).
The whole app is wrapped in an `AppErrorBoundary` (themed recovery panel).
Routes in `src/App.tsx`:

| Route | Component |
|---|---|---|
| `/` | Landing page (marketing) |
| `/pricing` | Pricing page |
| `/billing` | Billing page (P2) |
| `/usage` | Usage/cost dashboard (P6.5) |
| `/app` | Upload page |
| `/courses` | Course collections (P6.4) |
| `/share/:slug` | Public share redirect (P6.4) |
| `/process/:taskId` | Pipeline progress |
| `/workspace/:lectureId` | The 3-pane workspace |
| `/print` | Print/PDF route (`?type=…&lecture_id=…`) |

All API calls go through a single **typed API client** (`lib/http.ts`, P5.5):
`apiGet`/`apiPost`/`apiDelete`/`apiFetch`/`apiFetchRaw` merge auth headers, pass
`AbortSignal` through, and normalize errors into a typed `ApiError` (extracts
`detail`; non-JSON responses rejected). Return types derive from the
openapi-typescript `paths` schema (`ApiJson<P, M>`), so regenerating
`frontend/src/types/api.ts` from the backend's OpenAPI automatically tightens
every caller.

## 3.2 The 3-pane workspace

`Workspace.tsx` renders a CSS grid (`sidebar | doc | ai-panel`) with draggable,
keyboard-accessible resize separators (min/max constants). Escape toggles the
sidebar. The panels:

- **Sidebar** — lecture `<select>`, chapter list, thread list, quota badge,
  theme toggle.
- **DocPanel** — tab bar (Notes / Revision / Assessment / Guide / Mind map),
  search, PDF + interactive-export buttons. Since P6.4 the top bar also has a
  **Share** button opening `ShareModal` (creates the share link and copies it).
- **AIPanel** — tutor chat / quiz / flashcards, swapped with Framer transitions;
  width adapts between tutor mode (narrow) and quiz/cards mode (wide).

**Responsive tiers (UI/UX audit, in `8c4cd74`):** the workspace adapts to three
breakpoints — desktop (≥1024px) shows all three panes; tablet (768–1023px) shows
sidebar + doc with the AI panel in a slide-over drawer (a "AI" floating button
opens it, Escape/overlay closes); mobile (<768px) shows a single pane with
sidebar/doc/AI each becoming slide-over drawers, plus a floating **"Watch video"**
button (P6.3) that opens the docked YouTube player. These states share the same
components — the layout switches containers (CSS grid ↔ overlays) while panels
stay mounted, so state isn't lost. `PrintPage` is a separate route for clean
PDF/export output.

## 3.3 Zustand stores & state propagation

| Store | Purpose |
|---|---|
| `useLectureStore` | active `lectureId`, `lectures[]` |
| `useChapterStore` | active chapter, doc tab, sidebar collapsed |
| `useThreadStore` | threads, messages, streaming text, live references, per-thread cache |
| `useQuizStore` | AI mode, quiz session, answers/confidences, flashcards, ratings |
| `useAuthStore` | Supabase user/token + `refreshQuota()` (Part 5) |
| `useTutorSettingsStore` | persona, persisted per-lecture |
| `useCourseStore` | course collections + memberships (P6.4) |
| `useVideoStore` | current playback time / seek target / video open state (P6.3) |
| `useToastStore` | toasts |

**State propagation:** `lectureId` comes from the URL → `setActiveLecture` →
`loadChapters(lectureId)`. Every doc/chat/quiz/flashcard component reads the
active lecture (falling back to `'default'`) and the active chapter, then fetches
lecture-scoped API data. `lib/threadStorage.ts:getLectureId()` centralizes this,
scoping both API calls and localStorage keys per lecture.

## 3.4 Progress UI: polling, not SSE

`ProcessingPage.tsx` polls `GET /process/{taskId}/status` with `setInterval`,
**1.5s initially with exponential backoff up to 10s** (P4.5 hardened the poller:
AbortController on unmount, 404 → terminal error). A hardcoded `STAGES` array
drives a 16-step "rail"; completed stages get checkmarks, the active stage
pulses, and an animated "ink" line draws down (framer-motion, respects
`prefers-reduced-motion`). On `complete` → navigate to `/workspace/{taskId}`.
There's also a **Cancel** control → `POST /process/{id}/cancel`.

## 3.5 Tutor chat UI

- `ChatArea.tsx`: optimistic user message; streaming via
  `sendChatMessageStream`; the final assistant message commits under the
  **original thread id** even if the user switched threads mid-stream, with an
  atomic dedup guard.
- `MessageBubble.tsx`: user right, assistant left with ReactMarkdown
  (`remark-math` + `rehype-katex`). Since P5.6 the renderer is the shared
  `components/ui/Markdown.tsx` (`variant: doc|revision|print|chat`) — one
  component used by chat, notes, revision, study guide, and print; it also
  imports `katex.min.css` locally so marketing chunks never load KaTeX. The
  stream-heavy chat components are `React.memo`-wrapped so per-token re-renders
  skip re-parsing completed bubbles.
- **References**: `buildReferences()` renders note/screenshot citations;
  clicking a note ref switches chapter/tab if needed and smooth-scrolls to the
  DOM section (with a poll-until-mounted retry loop); screenshot refs open a
  Lightbox.
- **Highlight & Ask**: select text in `.doc-content` → floating "Ask Nora"
  button → posts "Explain this: <text>" to the tutor, adds it to the thread, and
  switches to tutor mode.

## 3.6 Quiz panel

- MCQ / True-False are **auto-graded instantly** (correct/incorrect styling +
  explanation); free-text is graded at the end by LLM (`POST /quiz/evaluate`).
- Per-question confidence buttons (Guess/Unsure/Confident/Very Confident).
- "Explain · where is this in the notes?" → `POST /quiz/explain` → `CitationBox`.
- Finish → `POST /quiz/attempts/:id/finish` → score ring + per-question LLM
  feedback + "Review Missed" (via `fetchQuizMissed`) + "Retake".

## 3.7 Flashcards

- Cards rated Again/Hard/Good/Easy, with a **3D flip** via Framer Motion
  (P6.2) driving `rotateY` on the card body (`perspective-1000` on the
  container), instead of the older pure-CSS `rotate-y-180`/`backface-hidden`
  approach.
- **P6.2 SM-2 spaced repetition** (`frontend/src/lib/flashcardSchedule.ts`): each
  rating advances the card's interval/repetitions/ease and moves it to the next
  due date; a "Due" filter shows cards whose due time has passed. Ratings persist
  keyed by **`getCardKey()` — a SHA-256 hash of the normalized front text**
  (`lib/hash.ts`), so they survive reloads even if deck structure changes.
- **Anki export** (P6.2): "Export .apkg" (`useQuizStore.exportAnkiDeck`)
  serializes the deck to Anki's `.apkg` format — a from-scratch writer that
  builds a SQLite archive with a JSON `collection.anki2` — so cards import into
  Anki with their SM-2 scheduling, with no third-party package.
- Filter to missed/due; stats footer derives Reviewed/Got it/Almost/Left from
  the current deck's card keys only.

## 3.8 Concept map (mind map)

- `lib/conceptMapLayout.ts` is the **single source of truth** for layout: a
  tree/radial placement algorithm (`layoutConceptMap(nodes, edges, 'tree'|'radial')`)
  and `conceptEdgePath()` cubic-bezier edges. Shared by the interactive
  `ConceptMapView`, the print `PrintConceptMap`, and inlined in the interactive
  HTML export.
- The `/concept-map` backend endpoint builds the graph with **zero LLM calls**
  from `lecture_outline.json` + chapter notes JSON.

## 3.9 Design tokens & theming

All tokens live in `src/index.css` under a Tailwind 4 `@theme` block:

- **"Drafting Vellum"** (light): parchment `#F6F2E7` backgrounds, ink text ramp
  (`nt`–`nt4`), red-pencil accent (`np`), hard-offset "blueprint" shadows
  (`3px 3px 0`).
- **"Blueprint at Night"** (dark): luminous Prussian `#0B1E3A`, cyan ink,
  light-edge shadows. The UI/UX audit (P6.4, `8c4cd74`) fixed dark-theme
  leftovers — code blocks/`<pre>` surfaces now get `--color-npbd` (a dark code
  background) instead of staying light, so dark mode has no glaring white slabs.
- **Type ramp** from `text-3xs` to `text-44`, plus a `text-hero` serif token.
- Signature decorative CSS: `.bg-blueprint-grid`, `.noise` (paper grain),
  `.fold-marks`, `.spec-label`, `.ripple`, `.scroll-highlight`, and a `@media
  print` block.
- Text-accent utilities (`text-np` etc.) get a tuned `-t` variant for 4.5:1
  contrast while solid fills stay saturated.
- Fonts: the audit added **Inter** for UI + **JetBrains Mono** for code (loaded
  via `@fontsource` in the theme), replacing system-font fallbacks.

## 3.10 Vite dev proxy

`vite.config.ts` proxies ~20 API paths (`/process`, `/chat`, `/quiz`,
`/notes`, `/study-guide`, `/quota`, `/billing`, `/concept-map`, `/courses`,
`/share`, `/video-map`, …) to `localhost:8000`, so the frontend uses relative
URLs and avoids CORS during dev. It `envDir: '..'` so Vite reads the repo-root
`.env`, and it `bypass`es text/html navigations to `/index.html` (so the SPA
router and API share the origin without a `/billing` collision).

---

# Part 4 — Micro-SaaS Foundation

Commit `5175684` took the working research app and added the skeleton of a paid
product: a Postgres schema, an auth layer, payment webhooks, usage metering, and
landing/pricing pages. `a12a387` then fixed QA bugs. The Supabase work in
`dacad59` (Part 5) *replaced* the initial auth scaffolding with a real auth
provider.

## 4.1 The schema & auth scaffolding (v1)

The same 5 tables (`users`, `subscriptions`, `lectures`, `usage_logs`,
`webhook_events`) with cascade deletes. The first auth version had a simplified
JWT/session check that `dacad59` replaced with real Supabase verification.

## 4.2 Lemon Squeezy webhooks

`backend/routers/webhooks.py` handles `POST /api/webhooks/lemonsqueezy`:

- **Signature verification:** HMAC-SHA256 of the raw body vs the `X-Signature`
  header using `LEMONSQUEEZY_WEBHOOK_SECRET`. Since P0 this is **fail-closed**:
  an unset secret rejects with 503 (dev escape hatch
  `NORAI_ALLOW_UNSIGNED_WEBHOOKS=1`), and a mismatch is a 401.
- **Idempotency:** event key = `data.id` / `meta.webhook_id` / stable SHA-256
  hash of the body; already-processed events return "Event already processed"
  without re-applying. (P0 replaced the process-randomized `hash()` fallback
  with a stable hash so Lemon Squeezy retries never double-apply.)
- **Tier/quota mapping:** an exact `PLAN_TIER_BY_VARIANT` table maps the variant
  name to a tier (P0 removed the spoofable `"pro" in variant` substring match).
- Handles `subscription_created` / `subscription_updated` (sets status, tier,
  quota, Lemon Squeezy ids) and `subscription_cancelled`.

Webhooks are how external billing events become DB state — no polling of the
payment provider.

## 4.3 Usage metering & quota enforcement (P2)

- `usage_logs` record per-stage input/output tokens + `estimated_cost_usd` per
  user/lecture. `backend/usage.py:record_pipeline_outcome` meters the lecture
  minutes + tokens on success *and* failure, and persists
  `Lecture.duration_seconds`/`status`.
- `subscriptions.monthly_minutes_quota` caps lecture minutes;
  `used_minutes_this_month` tracks spend.
- **Pre-spend enforcement** — `POST /process` requires auth (401), checks
  `used >= quota` (429), then the free-trial duration cap (429), then
  duration-aware `used + needed > quota` (429) — all *before* any
  download/Gemini spend. `GET /quota` returns the remaining budget. This is the
  free-trial → starter/pro funnel in code.
- **Billing page** — `GET /billing` returns plan/usage/subscription + Lemon
  Squeezy `checkout_urls`/`manage_url`; `BillingPage.tsx` renders tiers, a usage
  bar, and a manage-subscription section. The sidebar **quota badge** reads
  `/quota` through `useAuthStore.refreshQuota` (which only emits a new `user`
  object when the quota values actually change — otherwise an infinite
  refetch loop, a real P2 bug).
- **P6.5 usage/cost dashboard** — `backend/usage_ledger.py` aggregates the same
  per-stage rows into `GET /usage` (breakdown by lecture/stage/date, estimated
  $ cost), rendered by `UsagePage.tsx`. This is read-only metering — the same
  data that `usage_logs` already captures, rolled up for the user.

## 4.4 Landing & pricing pages

`LandingPage.tsx` — hero, tabbed interactive workspace mockup, "How It Works"
4-step stepper, features grid. `PricingPage.tsx` — monthly/annual toggle (SAVE
20%), 3 tiers (Free Trial $0 / Starter $11/$9 / Pro Student $29/$23), CTAs that
gate on auth. These were later polished in `f46b949` (Part 7).

## 4.5 The QA fix commit (`a12a387`) — lessons

- **Tutor memory** was the big one: `context_messages` was never populated, so
  the tutor had no conversation memory. Fixed in `load_memory_node` /
  `save_memory_node` (Part 2.6).
- **Missed questions:** `_compute_missed_ids` uses deterministic equality for
  MCQ/True-False and regex sentiment detection on the LLM remark for free-text —
  replacing a false-positive substring search.
- **Quiz auto-start bug:** removed a chapter-change effect that auto-started an
  all-difficulty quiz, overriding difficulty/missed/in-progress quizzes.
- **Flashcard stats** now derive from the current deck's card keys only.
- **Tutor dedupe window** hardened in `backend/dependencies.py`.

## 4.6 Courses & share links (P6.4)

- **Course collections** — `courses` + `course_lectures` tables; a lecture
  belongs to zero-or-one course via `course_id`. `POST /courses`, `GET /courses`,
  `POST /courses/{id}/lectures`, and `GET /courses/{id}` return course info plus
  its lectures. **Closed-by-default access:** a lecture is only returned to the
  owning user — reading a `course_id` you don't own or that isn't public fails
  closed. `CoursesPage.tsx` + `useCourseStore.ts` render the collection UI.
- **Share links** — `share_links` table stores a slug (`secrets.token_urlsafe(12)`
  unguessable id, used as the PK) + owner + optional `expires_at`. The
  **`ShareModal`** in DocPanel calls `POST /lectures/{id}/share` to mint a link;
  a **public** `GET /share/{slug}` returns a *sanitized* summary (title, PDF URL,
  few questions) with **no auth** and no data leak. `ShareRedirect.tsx` opens the
  public share page; the PDF route supports `?share=slug` for an unauthenticated
  PDF view. Public endpoints deliberately exclude quiz answers, raw transcripts,
  and the tutor.

---

# Part 5 — Supabase Auth + Postgres (the main event)

## 5.1 Architecture: what Supabase actually is

Supabase is a **hosted Postgres** database wrapped in open-source tooling:

- **Auth** — managed users, sessions, JWTs, email/OAuth/anonymous sign-in. You
  get an `anon` (public) API key and a `service_role` (secret, admin) key.
- **Postgres** — your actual database, exposed via `DATABASE_URL` for backend
  code (we don't use Supabase's JS `.from()` data layer at all — the Python
  backend talks to Postgres directly through asyncpg).
- **Storage / Edge functions / Realtime** — not used here (yet).

So our auth topology is:

```
Browser (supabase-js) ──issues JWT──▶ Supabase Auth
        │                                   ▲
        │  Bearer token in headers          │
        ▼                                   │
   FastAPI  ──verifies JWT via JWKS──▶ Supabase (certs)
        │
        ▼
   Postgres (asyncpg)  ← DATABASE_URL (Session pooler)
```

`supabase-js` never talks to our backend. It only talks to Supabase Auth to get
a JWT. That JWT is then passed to our FastAPI server in an `Authorization:
Bearer <token>` header.

## 5.2 JWT anatomy (know this cold)

A JWT is three base64url chunks joined by dots:

```
eyJhbGciOiJFUzI1NiIsImtpZCI6IjEi... . eyJzdWIiOiJ1c2VyX2lkIiw... . signature
       header                              payload                  signature
```

- **Header** — `alg` (signing algorithm) and `kid` (key id). `kid` tells the
  verifier *which* key from the JWKS set to use.
- **Payload** — the *claims*. For Supabase access tokens the important ones:
  - `sub` — the user id (this is our `users.id` primary key)
  - `aud` — audience. Supabase sets `authenticated` (email/OAuth/anon) or `anon`.
  - `exp` / `iat` — expiry / issued-at timestamps.
  - `email`, `user_metadata` (full_name, avatar_url), `is_anonymous`, `role`.
- **Signature** — cryptographic proof the token wasn't tampered with.

An access token is **short-lived** (1 hour by default). The browser also gets a
**refresh token** which Supabase-js uses silently to mint new access tokens, so
the user stays logged in. We only ever see/verify the access token.

## 5.3 HS256 vs ES256 (a real production gotcha)

| | HS256 | ES256 |
|---|---|---|
| Type | **Symmetric** — one shared secret | **Asymmetric** — private key signs, public key verifies |
| Sign & verify | Same secret | Private key (Supabase) / public key (you) |
| Your side needs | `SUPABASE_JWT_SECRET` | JWKS public keys |
| Rotation | Manual | Automatic — keys rotate, `kid` points to current key |
| Supabase default | Older projects | **Newer projects (this project)** |

If you hardcode HS256 verification but your Supabase project signs with ES256,
every decode fails. That's exactly why `backend/auth.py`:

1. reads the token's `alg` from the **unverified header**,
2. if `ES256` → fetch the signing key from the **JWKS endpoint** by `kid`,
3. if `HS256` → use `SUPABASE_JWT_SECRET` directly.

```python
alg = (pyjwt.get_unverified_header(token) or {}).get("alg", "")
if alg == "ES256" and _jwks_client is not None:
    key = _jwks_client.get_signing_key_from_jwt(token).key
elif alg == "HS256" and SUPABASE_JWT_SECRET:
    key = SUPABASE_JWT_SECRET
```

`PyJWKClient` is a `PyJWT` helper that fetches
`https://<project>/auth/v1/.well-known/jwks.json` once and **caches keys by
`kid`**, so verification doesn't hit the network every request.

## 5.4 The JWKS endpoint

JWKS = **J**SON **W**eb **K**ey **S**et. It's a standard endpoint publishing
public keys:

```json
{ "keys": [ { "kty": "EC", "kid": "1", "alg": "ES256", "x": "...", "y": "..." } ] }
```

Instead of sharing a secret, Supabase shares *public* keys. Anyone can fetch
them; only Supabase has the private signing key. This is how you verify a token
with **zero shared secrets**. Using JWKS also means key rotation Just Works —
when Supabase rotates keys, a new `kid` appears and `PyJWKClient` picks it up.

## 5.5 Fail-closed verification

`decode_supabase_jwt` is written to **fail closed**: any decode error, missing
`sub`, or unexpected `aud` returns `None` → the request is treated as
unauthenticated. No error is ever swallowed into a "success".

```python
try:
    payload = pyjwt.decode(token, key, algorithms=[alg], audience=list(ALLOWED_AUDIENCES))
except pyjwt.PyJWTError:
    return None
```

There's a dev-only escape hatch, `NORAI_DEV_INSECURE_AUTH=1`, that decodes
without signature verification — useful for local work without a live Supabase,
but it must never be set in production. Always fail closed.

The `aud` check (`authenticated`/`anon`) prevents **token confusion** — e.g. an
`anon` key being used where an authenticated session is required.

## 5.6 FastAPI dependencies: optional vs required auth

Two dependency functions in `auth.py`:

```python
# Returns User or None — safe for public-but-personalized routes
async def get_current_user_optional(credentials=Depends(security), db=Depends(get_db)):
    ...

# 401 if no valid user — for protected routes
async def get_current_user(user=Depends(get_current_user_optional)):
    if not user: raise HTTPException(401, ...)
    return user
```

`HTTPBearer(auto_error=False)` means "don't auto-401 when there's no header" —
so the optional variant can gracefully return `None`. Routes add:

```python
@app.get("/quota")
async def get_user_quota(user: Optional[User] = Depends(get_current_user_optional)):
```

## 5.7 Get-or-create user + default subscription

On first authenticated request, `get_or_create_user_from_token`:

1. Uses `sub` as the `users.id` (Supabase user id is the source of truth).
2. `SELECT` — if not found, insert `User` **and** a `Subscription` row
   (status `trial`, tier `free`, `monthly_minutes_quota = 15`).
3. Anonymous users get email `<user_id>@anonymous.norai` and `is_anonymous=True`.

```python
subscription = Subscription(
    user_id=user_id, status="trial", plan_tier="free",
    monthly_minutes_quota=15, used_minutes_this_month=0,
)
db.add(subscription)
```

The `/quota` endpoint reads `subscriptions.monthly_minutes_quota` vs
`used_minutes_this_month` and blocks processing when exhausted — the
foundation of the paid/trial monetization model.

> **P0 hardening (know these):** a duplicate-email race no longer silently
> demotes a real user to anonymous — an `IntegrityError` rolls back and
> re-fetches, and a missing `Subscription` is backfilled. `is_anonymous` now
> trusts the Supabase JWT `is_anonymous` claim, not the forgeable
> `@anonymous.norai` email suffix. `ensure_lecture_access` 404s artifact-read
> endpoints for foreign lectures when a token is presented.

## 5.8 Database wiring (async SQLAlchemy 2.0)

`backend/db/database.py`:

- `load_dotenv()` — makes sure `.env` is loaded even if imported standalone.
- `DATABASE_URL` resolves to env var, else falls back to SQLite for local dev.
- The driver is swapped: `postgresql://` → `postgresql+asyncpg://` because
  SQLAlchemy async engines need an async driver.
- `create_async_engine` + `async_sessionmaker(expire_on_commit=False)`.
- `get_db()` — async generator FastAPI dependency; commits on success,
  rolls back on exception, always closes.

**Schema management: Alembic since P4.3.** The app no longer uses
`Base.metadata.create_all` at boot. `backend/db/migrate.py:run_migrations()`
runs `alembic upgrade head` on every startup (idempotent), driven by
`alembic.ini` + `migrations/`. Migration revisions (newest last):

- `0001_initial_schema` — the base 5 tables.
- `0002_lecture_pipeline_job_columns` — adds the P4.1 job-queue columns
  (`stage`, `stage_message`, `progress`, `attempts`, `heartbeat_at`,
  `queued_at`, `started_at`, `cancel_requested`).
- `0003_usage_log_columns` — adds `model`, `calls`, `input_tokens`,
  `output_tokens` to `usage_logs` (P6.5 per-stage cost ledger).
- `0004_courses_and_shares` — the `courses`, `course_lectures`, `share_links`
  tables + `lectures.course_id` (P6.4).

`test_migrations.py` covers fresh-create + upgrade from a legacy `create_all`
DB. `create_all` only *creates* missing tables; it can't alter existing ones —
that's exactly why Alembic was introduced the moment the schema changed (see
interview Q below).

## 5.9 The schema (`models.py`)

8 tables with FK relationships and cascade deletes:

```
users 1──1 subscriptions      (user_id unique, cascade delete)
users 1──N lectures           (cascade delete)  ← also the job-queue row (P4.1)
users 1──N usage_logs         (cascade delete)
lectures 1──N usage_logs      (cascade delete)
webhook_events                (idempotency key = Lemon Squeezy event id)
users 1──N courses            (P6.4; cascade delete)
courses 1──N course_lectures  (P6.4)
users 1──N share_links        (P6.4; owner, slug, expires_at)
lectures 0..1──1 course_id    (P6.4; set on lecture)
```

- `User.subscription` is `uselist=False` (one-to-one).
- Foreign keys use `ondelete="CASCADE"` so deleting a user cleans up all their
  data — required by data-privacy law and plain good hygiene.
- `usage_logs` store per-stage token counts + `estimated_cost_usd` — used to
  meter real LLM spend per user; since `0003` also record `model` + `calls`.
- `Lecture` doubles as the **job queue row**: `status`
  (`queued|processing|completed|failed|cancelled`), `stage`, `progress`,
  `attempts`, `heartbeat_at`, `cancel_requested` (P4.1).
- `Course`, `CourseLecture`, `ShareLink` (P6.4) model collections and public
  share links — a `ShareLink` row can optionally carry `expires_at`, and a
  `Course` has `is_public` toggling whether non-members can read its lectures.

## 5.10 Frontend Supabase client

`frontend/src/lib/supabaseClient.ts`:

```ts
export const supabase = createClient(
  supabaseUrl || 'https://placeholder.supabase.co',
  supabaseAnonKey || 'placeholder-anon-key',
)
```

- Reads `import.meta.env.VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY`.
- Placeholders are deliberate — the app boots even without env vars (auth just
  won't work), so CI/preview doesn't crash.
- Uses the **`anon` key**: it's public by design. Anyone can read it; the real
  security comes from Supabase RLS + our backend verifying the JWT signature.

## 5.11 Auth state store (Zustand + subscription)

`useAuthStore.ts` is the single source of auth truth in React:

```ts
initAuth: async () => {
  const { data } = await supabase.auth.getSession()        // rehydrate on reload
  const { token, user } = mapSession(data.session)
  set({ token, user })
  supabase.auth.onAuthStateChange((_event, session) => {    // live updates
    set({ ...mapSession(session), isAuthModalOpen: false })
  })
}
```

Two critical patterns:

1. **`getSession()` on app start** — Supabase persists the session in
   localStorage, but the store is empty on reload. We must read it back
   (rehydrate) or the UI would think you're logged out.
2. **`onAuthStateChange` subscription** — any auth event (login, signout, token
   refresh) updates the store reactively. This is what makes the whole app
   update without manual wiring.

`main.tsx` calls `initAuth()` once before rendering the app.

## 5.12 Bearer injection everywhere

`authHeaders.ts` reads the token from the store (works outside React — that's
why the store is module-level) and returns an `Authorization` header:

```ts
export function authHeaders() {
  const token = useAuthStore.getState().token
  return token ? { Authorization: `Bearer ${token}` } : {}
}
```

Used by `apiFetch()` and both `sendChatMessage` / `sendChatMessageStream`, which
merge it with `Content-Type`. This is how `/chat`, `/chat/stream`, `/process`
and `/quota` all become authenticated.

## 5.13 AuthModal: the four real flows

`AuthModal.tsx` now calls the real Supabase SDK:

- **Sign up** — `supabase.auth.signUp({ email, password, options: { data: { full_name } } })`.
  If no `data.session` comes back, the project requires **email confirmation**
  → show "check your inbox" notice. (Some providers auto-confirm; Supabase
  defaults to requiring confirmation for real domains.)
- **Log in** — `signInWithPassword({ email, password })`. On error,
  `err.message` is shown in a banner.
- **Google** — `signInWithOAuth({ provider: 'google', options: { redirectTo } })`.
  Full-page OAuth redirect; the callback URL must be whitelisted in the dashboard.
- **Guest** — `signInAnonymously()`. Produces a normal JWT (aud `authenticated`)
  with `is_anonymous=true`. **Requires the Anonymous provider to be enabled** in
  the Supabase dashboard — this burned us once (it was off by default).

## 5.14 Vite config: envDir + proxy

```ts
envDir: '..',
```

Tells Vite the `.env` file is **one directory up** (repo root, not `frontend/`).
Vite only exposes `VITE_*`-prefixed vars to the browser via `import.meta.env`.
Server-only secrets (`DATABASE_URL`, `SUPABASE_JWT_SECRET`) stay private.

The dev proxy forwards API paths to `localhost:8000`, including the new
`/quota`. The proxy sidesteps **CORS** during dev and lets the frontend use
relative URLs.

## 5.15 Real-world gotchas we hit (memorize these stories)

1. **IPv6-only DB host.** Supabase's direct host `db.<ref>.supabase.co` only
   resolves to IPv6. This machine has no IPv6 route → connection timeout. Fix:
   use the **Session pooler** `aws-0-ap-southeast-2.pooler.supabase.com:5432`
   which has IPv4. Always prefer the pooler (it also handles connection limits).
2. **ES256, not HS256.** New Supabase projects sign with ES256 per-project keys.
   Verification MUST use JWKS. This was a hard-won lesson baked into `auth.py`.
3. **Anonymous auth disabled by default.** `signInAnonymously` errors until you
   toggle "Allow anonymous sign-ins" in the dashboard.
4. **Email confirmation UX.** Sign-up returns no session when confirmation is on
   — you must handle the "check your inbox" path, not assume instant login.
5. **Google OAuth needs dashboard setup.** The button is wired, but the provider
   must be enabled and the redirect callback added before it works.

---

# Part 6 — PDF & Print Exports

## 6.1 The approach: print the DOM, not a PDF library

Rather than a heavy PDF library, we open a dedicated print route and call
`window.print()`. The user's browser dialog offers **"Save as PDF"**. This gives
perfect CSS fidelity for free and needs zero backend work.

```
/print?type=notes|revision|guide|concepts|assessment&lecture_id=…
  → PrintPage → usePrintData fetches chapter data
  → setTimeout(window.print(), 3000)   // after data is painted
```

## 6.2 CSS print control

The browser splits content into pages. We control the splits with:

```css
.print-flow h1 {
  break-after: avoid;        /* don't leave a heading stranded at page bottom */
}
.print-flow + .print-flow {
  break-before: auto;        /* continuous flow */
}
```

- `break-inside: avoid` — keeps a block (card, chapter) from being split.
- `break-after: avoid` — keeps a heading attached to what follows it.
- `@media print` — the print styles only apply when printing.

## 6.3 Continuous flow vs page-per-chapter

Two different intents:

- **Notes / assessment** — one chapter per page (each chapter starts a fresh
  page) — easier to study page-by-page.
- **Revision / guide** — **continuous flow** (`.print-flow`), like the on-screen
  deck, so it reads like a long document without huge whitespace gaps.

The type is chosen in `PrintPage.tsx`:

```tsx
<PrintChapter ... continuous={type === 'revision'} />
```

## 6.4 Concept maps → static SVG

The on-screen mind map is an interactive canvas. For print we render the *same
layout data* (`conceptMapLayout.ts` — shared so screen and print match) as static
vector SVG, so it prints crisply at any scale and weighs almost nothing.

## 6.5 Interactive HTML export

For people who want the *interactive* mind map offline, a self-contained HTML
file (pan/zoom, clickable nodes, chapter tabs) is generated client-side with
`exportInteractiveMindmap.ts` — inline CSS/JS in one `<html>` file, no external
dependencies.

---

# Part 7 — Landing/Pricing Review Pass

A pure-frontend polish commit, but the concepts matter:

- **Design tokens** — spacing/type-scale values centralized in `index.css`
  (e.g. `text-22-bold`, `text-10-medium`) instead of magic numbers scattered
  through components. Consistency + easy theming.
- **Type-scale** — a deliberate set of font sizes (10/12/22/…) rather than
  arbitrary values, so headings and body copy feel designed.
- **Accessibility (a11y)** — focus states, color contrast, semantic labels,
  keyboard-navigable controls, no overflow-on-mobile.
- **Mobile overflow** — content must not force horizontal scroll on narrow
  viewports (`overflow-x` guards, responsive widths).

---

# Part 8 — P0→P7 Hardening (the production pass)

After the feature work, several hardening phases shipped (see the commit table).
These are the concepts interviewers will probe most:

## 8.1 P0 — Security hardening

- **Webhook fail-closed** — unset secret → 503; mismatch → 401; stable
  SHA-256 idempotency; exact `PLAN_TIER_BY_VARIANT` table (no spoofable
  substring match).
- **Static allowlist** — `/static` is no longer a blanket mount. An
  image-only allowlist (`resolve_static_path`) means transcripts, answer keys,
  `checkpoints.sqlite`, Chroma DBs, and `backend.log` are **not servable**;
  traversal is blocked.
- **`/process` input gate** — `source_type` validated; YouTube/Drive URLs must
  pass `is_youtube_url`/`is_gdrive_url` (kills **SSRF** before download); upload
  extension whitelist (415) + `NORAI_MAX_UPLOAD_BYTES` cap (413); upload
  auto-deleted after the pipeline finishes.
- **Error sanitization** — raw exception details leak only to logs; a global
  exception handler returns generic 500s.
- **Auth fixes** — duplicate-email race resolved; `is_anonymous` trusts the JWT
  claim; `ensure_lecture_access` ownership scoping on read endpoints.

## 8.2 P1 — Pipeline economics (see 1.13)

Hash-of-inputs caching, batched/diff-synced Chroma indexing, adaptive chunking,
duplicate-analysis removal, self-calibrating `POST /estimate`. A full lecture
dropped from ~128 → ~35 Gemini calls; re-runs cost **0**.

## 8.3 P2 — Billing & quota (see 4.3)

Usage metering (`backend/usage.py`), pre-spend quota enforcement on
`POST /process` (401/429 before any Gemini), `/quota` + sidebar badge,
`/billing` + BillingPage, Lemon Squeezy checkout/manage URLs.

## 8.4 P3 — Retrieval & tutor hardening (see 2.3/2.8)

Hybrid BM25+RRF retrieval, context expansion, verified citations,
cross-turn chapter state, bounded memory (`RemoveMessage`), low-context
statuses, and a golden-QA eval harness (`tutor/evals/`).

## 8.5 P4 — Job durability & async persistence (see 1.2/1.3)

- DB-backed job queue (`backend/jobs.py`): supervisor + bounded worker pool,
  heartbeat-stale recovery, retry-with-backoff (≤ `PIPELINE_MAX_ATTEMPTS`),
  global + per-user concurrency caps, GC sweep (P4.2).
- Alembic migrations (`migrations/`, `backend/db/migrate.py`).
- Async tutor persistence (P4.4): `AsyncSqliteSaver`, async graph nodes,
  per-lecture `asyncio.Lock`, LRU graph cache.
- SSE scaffolding removed (P4.5): progress is DB-persisted + polled.

## 8.6 P5 — Foundation (observability, deps, CI, Docker, frontend hygiene)

- **P5.1 observability** — `backend/logging_config.py` structured JSON logs
  (console + rotating `outputs/backend.log`); `request_id` middleware
  (accepts/echoes `X-Request-ID`); contextvars binding of
  `lecture_id`/`thread_id`; `tutor/llm.py` `UsageLoggingChatLLM` writes
  per-call token usage to `outputs/llm_calls.jsonl`.
- **P5.2 dependency hygiene** — `requirements.txt` exact-pinned to what's
  imported; `requirements-dev.txt`; `.env.example` committed.
- **P5.3 CI** — `.github/workflows/ci.yml` runs backend offline tests +
  frontend `npm ci`/oxlint/`tsc -b`/`vite build`/`vitest`.
- **P5.4 Docker** — single-container multi-stage image (`Dockerfile`):
  node:20-alpine builds the SPA, python:3.12-slim runs FastAPI **and serves
  the built SPA** (`NORAI_SPA_DIST=/app/frontend/dist`, text/html requests →
  `index.html`; API JSON routes unaffected). `docker-compose.yml` maps
  `8000:8000`, loads repo-root `.env`, mounts `norai_outputs` on
  `/app/outputs`. Two real build fixes: `frontend/.npmrc`
  (`legacy-peer-deps=true` — openapi-typescript 7 peer-requires TS ^5 but the
  repo pins ~6), and six exact pins added to `requirements.txt` (gdown,
  imagehash, numpy, pillow, langgraph, langgraph-checkpoint-sqlite).
- **P5.5 typed API client** — `lib/http.ts` (see 3.1); `strict: true`.
- **P5.6 bundle & resilience** — lazy routes, single `Markdown` renderer,
  app-level `AppErrorBoundary`, `React.memo` chat components (see 3.1/3.5).
- **P5.8 tests** — Vitest 4 + React Testing Library (38 tests: `parseChapter`,
  `references`, `http`, `conceptMapLayout`, `Markdown`, `AppErrorBoundary`,
  `useQuizStore`) and `backend/test_api_contract_offline.py` (15 checks that
  boot the app in-process with lifespan startup against a temp SQLite DB —
  migrations, supervisor, GC all run). `scripts/run-tests.sh` runs every
  offline `test_*.py` (the live-server probe stays excluded).

## 8.7 P6 — Retention (streaming, SRS, video grounding, courses/sharing, usage)

- **P6.1 real token streaming** — `/chat/stream` drives the graph with
  `graph.astream_events(version="v2")` and forwards only the
  `on_chat_model_stream` events from the answer node (`metadata['langgraph_node']
  == 'generate_answer'`), so the answer node must call `llm.astream(...)`
  (see 2.10). Cached/stream-miss answers replay as a single frame with a
  `final` flag; the frontend dedupes by frame counter.
- **P6.2 spaced repetition + Anki** — SM-2 scheduling (`frontend/src/lib/flashcardSchedule.ts`)
  with per-rating due-date progression; a "Due" filter; `.apkg` export
  (`useQuizStore.exportAnkiDeck`, a from-scratch Anki writer — SQLite archive +
  JSON collection, no third-party package). Framer Motion 3D card flip replaced
  the CSS-only flip (see 3.7).
- **P6.3 click-to-video grounding** — the visual stage persists per-chapter
  YouTube seek maps (`backend/video_map.py`, `lecture_video_seek_maps.json`);
  the frontend derives per-section seek targets, and a docked player
  (`useVideoStore`) seeks on chapter change and on "Watch video" buttons
  (see 3.2). This shipped with a timestamp-persistence bugfix (visual stage no
  longer overwrites the DB timestamp with a placeholder).
- **P6.4 courses & sharing** — course collections + closed-by-default share
  links (see 4.6). Migrations `0003`/`0004`. Frontend: `CoursesPage`,
  `ShareModal`, `ShareRedirect`, `useCourseStore`, custom `Select`.
- **P6.5 usage/cost dashboard** — `backend/usage_ledger.py` aggregates the
  per-stage `usage_logs` (now with `model`/`calls` columns, migration `0003`)
  into `GET /usage`; `UsagePage.tsx` renders cost/usage breakdowns (see 4.3).

## 8.8 P7 — Token reduction (see `docs/token_reduction.md`)

- **Prompt compression** — the tutor's system prompt was slashed to a lean
  instruction set (~1.5k → ~0.3k tokens); retrieval prompts trimmed; default
  answer length shortened.
- **Context caching** — `context_caching_config` wired for the system prompt,
  so repeated tutor calls hit the cached prefix. Implemented but currently
  **dormant**: the app runs on Gemini's free tier where caching isn't enabled,
  so the flag is off by default and can be toggled on a paid plan.
- **Output-token cut** — `max_output_tokens` lowered across pipeline/tutor
  calls and the `/chat` temperature raised slightly to leaner phrasing; verified
  via a before/after cost run in `docs/token_reduction.md`.

## 8.9 UI/UX audit execution

The frontend redesign driven by `UI_UX_AUDIT_REPORT.md` shipped in `8c4cd74`
(see Part 3 for details): three responsive tiers for the workspace (desktop /
tablet slide-over / mobile single-pane), skeleton loading states across views,
a custom keyboard-accessible `Select` replacing the native `<select>` on
UploadPage, dark-theme code surfaces (`--color-npbd`) and contrast fixes,
Inter + JetBrains Mono fonts, and the course/share pages. Verified by
70 Vitest tests, backend `test_courses_shares.py` (37 checks) + `test_migrations.py`
(21 checks), oxlint clean, and `tsc -b`/`vite build` green.

---

## Concepts Glossary

| Term | Meaning |
|---|---|
| **JWT** | Signed JSON token with header + payload + signature |
| **JWKS** | URL publishing public keys used to verify JWTs (auto-rotation) |
| **Bearer token** | `Authorization: Bearer <token>` — "whoever holds it, is it" |
| **HS256** | Symmetric signing (shared secret) |
| **ES256** | Asymmetric signing (private signs, public verifies) |
| **`sub`** | Subject claim = user id |
| **`aud`** | Audience claim — restricts which app/token-type is valid |
| **OAuth** | Delegated auth (Google): redirect to provider, get token back |
| **Anonymous auth** | Instant session without credentials, tied to a browser |
| **Refresh token** | Long-lived token that mints new access tokens |
| **PKCE** | OAuth challenge: verifier + code_challenge (mobile/SPA) |
| **Rehydration** | Reading persisted session state back into memory on reload |
| **ORM** | Object-Relational Mapping — tables ↔ Python objects |
| **asyncpg** | Async PostgreSQL driver for Python |
| **create_all** | SQLAlchemy: create tables that don't exist (no altering) |
| **Alembic** | Real DB migration tool (schema versioning) |
| **Cascade delete** | Deleting parent auto-deletes children |
| **Session pooler** | Supabase's IPv4-reachable PgBouncer-like endpoint |
| **Vite proxy** | Dev server forwards `/api` → backend, bypassing CORS |
| **`import.meta.env`** | Vite env access in browser; only `VITE_*` exposed |
| **`break-inside` / `break-after`** | CSS page-break control for print |
| **Fail closed** | On error, deny (return None/401) rather than allow |
| **CORS** | Browser same-origin policy; proxy avoids it in dev |
| **Pipeline orchestration** | Coordinating many stages with status/progress/error handling |
| **ThreadPoolExecutor** | Python concurrent branch execution across threads |
| **Supervisor thread** | Daemon thread that polls the DB, claims + recovers pipeline jobs (P4) |
| **Heartbeat** | Periodic DB timestamp proving a job is alive (stale ⇒ re-queue) |
| **Job queue** | DB rows in `lectures` act as the durable queue (P4.1) |
| **SSE** | Server-Sent Events — one-way server→client stream (`data:` frames) |
| **Polling** | Client repeatedly fetches status instead of receiving pushes |
| **RAG** | Retrieval-Augmented Generation — retrieve context, then generate |
| **Vector store** | DB that searches by embedding similarity (ChromaDB) |
| **Embedding** | Dense numeric vector representing text meaning |
| **Asymmetric embedding** | Documents and queries formatted differently before embedding |
| **BM25** | Classic lexical (keyword) retrieval scoring |
| **RRF** | Reciprocal Rank Fusion — merge two ranked lists by rank, not score |
| **Hybrid retrieval** | Combining dense (embedding) + sparse (BM25) signals |
| **Verified citation** | Deterministic post-check that an answer's Sources came from retrieval |
| **LangGraph** | Framework for stateful LLM graphs with checkpoints |
| **Checkpointer** | Persists graph state so conversations survive restarts |
| **`AsyncSqliteSaver`** | Async LangGraph checkpointer backed by SQLite (P4.4) |
| **Structured output** | LLM forced into a Pydantic/schema shape; validate + retry |
| **Perceptual hash (pHash)** | Image fingerprint for near-duplicate detection |
| **Hash-of-inputs caching** | `.sha256` markers skip stages whose inputs didn't change (P1.4) |
| **Diff-sync indexing** | Compare content-hashed ids; add/remove only the delta (P1.2) |
| **Webhook** | Provider calls your URL on an event; no polling |
| **HMAC-SHA256** | Keyed message signature used to verify webhook origin |
| **Idempotency** | Same event processed once even if delivered repeatedly |
| **Usage metering** | Recording tokens/cost per user for billing |
| **Pre-spend enforcement** | Reject a request *before* it costs money (P2) |
| **Design tokens** | Centralized style values (colors/spacing/type) in CSS |
| **Type-scale** | Deliberate, ordered set of font sizes |
| **Zustand** | Tiny React state store with `getState()` outside components |
| **Optimistic update** | Show the change before the server confirms |
| **Code splitting** | `React.lazy` — load a route's JS only when visited (P5.6) |
| **Typed API client** | One wrapper deriving response types from the OpenAPI schema (P5.5) |
| **Vitest** | Fast Vite-native JS test runner (P5.8) |
| **SM-2** | Spaced-repetition algorithm — interval/repetitions/ease from a rating (P6.2) |
| **`.apkg`** | Anki's package format — SQLite archive + JSON collection (P6.2) |
| **`astream_events`** | LangGraph's async event stream — yields `on_chat_model_stream` for token streaming (P6.1) |
| **Seek map** | Per-chapter YouTube timestamp→section map used for click-to-video (P6.3) |
| **Course** | User-owned collection of lectures (`courses`/`course_lectures`, P6.4) |
| **Share link** | Slug-keyed public URL exposing only sanitized content (P6.4) |
| **Closed-by-default** | Access model — data is private unless explicitly shared (P6.4) |
| **Context caching** | Reusing a cached prompt prefix across calls to cut input tokens (P7; dormant) |
| **Prompt compression** | Shrinking system/user prompts to reduce token cost (P7) |
| **Skeleton loading** | Placeholder shimmer while async data loads (UI/UX audit) |

---

## Developer Cheat-Sheet

**Commands** (from repo root):

```bash
./scripts/start-dev.sh {start|stop|status}   # backend :8000 + frontend :5173
venv/bin/python -m uvicorn backend.main:app --reload --port 8000   # backend alone
cd frontend && npm run dev                   # vite :5173
cd frontend && npm run lint                  # oxlint
cd frontend && npm run test                  # vitest (frontend tests, P5.8)
cd frontend && npm run build                 # tsc -b && vite build
venv/bin/python tutor/test_chunker.py        # standalone offline test scripts (no pytest)
scripts/run-tests.sh                         # run ALL offline test_*.py (CI does this)
docker build -t norai . && docker compose up -d   # P5.4 single-container
```

**Gotchas to remember:**

- Launch backend with `-m` from repo root (needs `config.py` importable).
- Health-check via HTTP probe, not log-file size.
- Never relaunch over an occupied port (uvicorn spins at 120% CPU).
- npm lives under nvm here — no `/usr/bin/npm`; use `start-dev.sh` or `$(command -v npm)`.
- Node 20+ is required (Vite 8 / TS ~6); the Docker image uses `node:20-alpine`.
- **All pipeline stages cost Gemini tokens — don't run the pipeline casually.** Re-runs of the same lecture id are ~0 (P1 caching).
- The free-trial gate blocks lectures > 15 min (`MAX_FREE_DURATION_MIN`).
- Most pipeline stages tolerate failure — check `outputs/<id>/backend.log`.
- `.env` (repo root) holds secrets: `DATABASE_URL`, `SUPABASE_JWT_SECRET`,
  `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `LEMONSQUEEZY_WEBHOOK_SECRET`. Never commit it; `.env.example` is committed.
- Anonymous + email providers must be enabled in the Supabase dashboard.
- `outputs/` and `.tmp/` are throwaway — never commit.

**Key file map:**

- `backend/orchestrator.py` — pipeline runner + progress (synchronous, worker-owned)
- `backend/jobs.py` — DB-backed job queue: supervisor, worker pool, GC (P4)
- `backend/lecture_registry.py` — lecture dirs/registry
- `backend/auth.py` — JWT verification + auth dependencies
- `backend/db/database.py` — async engine + session
- `backend/db/migrate.py` + `migrations/` — Alembic schema migrations (P4.3)
- `backend/db/models.py` — 8-table schema (+ Lecture job-queue columns, courses/shares)
- `backend/usage.py` / `backend/usage_ledger.py` / `backend/estimator.py` / `backend/ratelimit.py` — metering, cost dashboard, estimate, rate limits (P1/P2/P6.5)
- `backend/logging_config.py` / `tutor/llm.py` — structured logs + LLM usage tracking (P5.1)
- `backend/routers/webhooks.py` — Lemon Squeezy billing events
- `backend/video_map.py` — per-chapter YouTube seek-map extraction (P6.3)
- `tutor/cache.py` — answer-cache helpers used by streaming (P6.1/P7)
- `tutor/graph.py`, `tutor/nodes.py`, `tutor/nodes_retrieval.py`, `tutor/retriever.py`, `tutor/bm25.py`, `tutor/citations.py`, `tutor/embedding.py`, `tutor/memory.py` — RAG tutor
- `tutor/evals/` — golden-QA eval harness (P3)
- `frontend/src/stores/*` — Zustand stores (auth, lecture, chapter, thread, quiz, course, video)
- `frontend/src/lib/http.ts` — typed API client (P5.5)
- `frontend/src/components/ui/Markdown.tsx` — shared markdown renderer (P5.6)
- `frontend/src/components/AppErrorBoundary.tsx` — app-level error boundary (P5.6)
- `frontend/src/pages/CoursesPage.tsx` + `components/ui/Select.tsx` — course collections UI + custom a11y select (P6.4)
- `frontend/src/components/doc/ShareModal.tsx` + `pages/ShareRedirect.tsx` — share-link minting + public share view (P6.4)
- `frontend/src/pages/UsagePage.tsx` — usage/cost dashboard (P6.5)
- `frontend/src/lib/flashcardSchedule.ts` (SM-2) + `stores/useQuizStore.ts` (`exportAnkiDeck`, P6.2)
- `frontend/src/components/video/VideoPlayer.tsx` + `lib/video.ts` + `stores/useVideoStore.ts` — click-to-video (P6.3)
- `frontend/src/lib/supabaseClient.ts` — supabase-js client
- `frontend/src/lib/authHeaders.ts` — Bearer injection
- `frontend/vite.config.ts` — `envDir: '..'` + proxy
- `frontend/src/components/PrintPage.tsx` — print/PDF route
- `Dockerfile` / `docker-compose.yml` — single-container deploy (P5.4)
- `.github/workflows/ci.yml` / `scripts/run-tests.sh` — CI + offline test runner (P5.3)

---

## Interview Prep — Q&A

### Pipeline & Async

**Q: How did you run a long AI pipeline without blocking the API server?**
A: `POST /process` **enqueues a `Lecture` row** (`status="queued"`); a
**supervisor thread** in `backend/jobs.py` polls the DB, claims the job within
global + per-user concurrency caps, and runs the fully synchronous pipeline
(`run_pipeline`) in a worker thread from a bounded `ThreadPoolExecutor`. FastAPI
stays responsive, and the frontend polls `GET /process/{id}/status` (DB-backed).
Inside, the two independent branches — text (transcribe → chunk → extract) and
visual (frames → scenes) — run in parallel with a `ThreadPoolExecutor(max_workers=2)`.

**Q: Why a background thread instead of an async task?**
A: The pipeline makes long blocking calls (FFmpeg, Faster-Whisper, Gemini HTTP).
Running those on the event loop would block every other request. A worker thread
keeps the server responsive. Blocking LLM calls in request handlers are
similarly offloaded with `asyncio.to_thread`, and the tutor's own LLM calls are
`async` (P4.4).

**Q: Why a DB-backed job queue instead of spawning threads directly?**
A: Durability + bounded concurrency. If the server restarts, the `lectures` rows
still say `queued`/`processing`, so the supervisor **recovers** them —
a `processing` job with a stale heartbeat is re-queued (up to
`PIPELINE_MAX_ATTEMPTS`) or marked `failed`. Because every pipeline stage is
cache-first (P1.4), a recovered job resumes at ~0 Gemini calls. The queue also
enforces a global cap (`MAX_CONCURRENT_PIPELINES`) and a per-user cap
(`MAX_PER_USER_PIPELINES`) that a pile of raw threads never could.

**Q: How does progress get from the worker to the frontend?**
A: The worker calls an `on_progress(stage, message, percent)` callback that
**persists to the `lectures` DB row** and refreshes `heartbeat_at`; the status
endpoint reads the DB. The frontend **polls** `/process/{id}/status` with
exponential backoff (1.5s → 10s). We deliberately **dropped the SSE push
scaffolding** in P4.5 — the old `_queues`/`run_coroutine_threadsafe` code was
dead weight (no endpoint ever registered a queue). The only real SSE in the app
is `/chat/stream` (Part 2.10).

**Q: How did you make the pipeline resilient to failures?**
A: Two layers. **Partial-failure tolerance:** only hard-dependency stages
(ingestion, duration check, the two parallel branches) fail the run; everything
from mapping onward is wrapped in try/except that logs and continues, and
outline generation writes a single-chapter fallback on failure. **Job-level
retries:** a failed run with attempts left is re-queued by the supervisor and
resumed cache-first (P4.1) — cheap because unchanged stages skip via hash-of-inputs.

**Q: What does the 15-minute free-trial gate do?**
A: Two gates. At the **API layer** (P2), `POST /process` rejects 401 (no auth)
or 429 (quota exhausted / duration over `MAX_FREE_DURATION_MIN`) *before* any
download or Gemini spend. In the **pipeline**, after ingestion it re-reads the
duration and raises if it exceeds `MAX_FREE_DURATION_MIN` while
`ENFORCE_FREE_TRIAL_DURATION=true`. Defense in depth: the cheap pre-flight check
stops the spend, the in-pipeline check catches anything that slips through.

**Q: Why one LLM call per chapter instead of one per artifact?**
A: Cost. `generate_consolidated_chapter_artifacts` makes a single Gemini call
per chapter with `response_schema=MergedChapterArtifactsModel` returning notes
sections + revision summary + assessment questions (with embedded flashcard
fields). Four artifact types, one paid call. Flashcards are then a pure
transform — zero extra LLM calls. Combined with P1's hash-of-inputs caching and
diff-synced indexing, a full lecture costs ~35 calls and a re-run costs 0.

### RAG & Embeddings

**Q: Walk me through the RAG flow.**
A: `load_memory` rebuilds the prompt window → `detect_chapter` scopes to the
chapter (and remembers `last_chapter_id` for anaphoric follow-ups) →
`rewrite_query` makes the question self-contained → `retrieve` (hybrid
dense+BM25 with RRF fusion) + `retrieve_images` query the per-lecture Chroma
indexes (filtered by `chapter_id`) → `generate_answer` injects the results as
CONTEXT SystemMessages into a Gemini prompt → `verify_citations` deterministically
checks the answer's Sources against the retrieved chunk ids → `save_memory`
summarizes when history grows. Grounded in the lecture, not the model's general
knowledge — and the citations you see in the UI are verified, not LLM-claimed.

**Q: Why did you write a custom Chroma embedding function?**
A: The built-in Chroma wrapper only documents `gemini-embedding-001` and passes a
`task_type=` parameter, but **`gemini-embedding-2` removed `task_type`** — task
instructions go in the prompt text instead. My `GeminiEmbeddingFunction` formats
documents as `"title: … | text: …"` and queries as
`"task: question answering | query: …"` (asymmetric), wraps each string in its
own `Content`, and retries with exponential backoff.

**Q: Why hybrid retrieval (dense + BM25)?**
A: Dense embeddings capture semantic similarity but miss exact terms, numbers,
and acronyms; BM25 matches those precisely but ignores meaning. We fuse both
with **Reciprocal Rank Fusion** (60/40 dense/sparse) — combine the *rank* of each
result from both lists rather than raw scores, which are on different scales.
This measurably raised hit-rate on the golden-QA eval suite (P3).

**Q: Why two Chroma collections and where-filtering?**
A: `norai_notes` holds study-note chunks (with `heading`, `heading_path`,
`chapter_id`, `source` metadata); `screenshot_captions` holds screenshot reasons
(with `path`, `section`, `importance`, `chapter_id`). Queries use `where=
{"chapter_id": {"$eq": n}}` so retrieval is scoped to the active chapter, and
images sort by `(distance asc, importance desc)` so the best + most relevant
win.

**Q: How did you give the tutor long-term memory without huge prompts?**
A: Windowing + incremental summarization. Each turn, `load_memory_node` rebuilds
the prompt window as the **latest summary SystemMessage + the last 6 Human/AI
messages**. Once 12+ new turns accumulate, `save_memory_node` LLM-summarizes all
but the most recent 6 into a `CONVERSATION SUMMARY:` record and returns
**`RemoveMessage`s** so the checkpoint store stays bounded too. This was a real
bug fix — the tutor was previously stateless.

**Q: How do you verify what the model "knows" is actually in the lecture?**
A: We don't trust it blindly — three layers. (1) Retrieval is always scoped to
the lecture's own index with `where={chapter_id}`. (2) A **low-confidence mode**:
if every retrieved chunk exceeds the confidence threshold, the context block
tells the model to express uncertainty instead of hallucinating; retrieval
failures get their own distinct prompt note (`retrieval_status` = ok/empty/error).
(3) **Verified citations**: after generation, `verify_citations_node`
deterministically post-checks the answer's Sources against the retrieved chunk
ids (no LLM), and the UI renders only verified citations.

### Frontend Architecture

**Q: How does lecture identity propagate through the whole UI?**
A: `lectureId` comes from the URL → `useLectureStore.setActiveLecture` →
`loadChapters`. Every component reads the active lecture/chapter from stores and
calls lecture-scoped APIs. `threadStorage.ts:getLectureId()` centralizes it so
both API calls and localStorage keys are namespaced per lecture — preventing
cross-lecture state leakage.

**Q: Why Zustand over Context/Redux?**
A: Zustand is lightweight, needs no provider, and — critically — is a module
singleton importable from **non-React code** (`useAuthStore.getState().token` in
`authHeaders.ts`). It also avoids re-render cascades since selectors subscribe
to slices.

**Q: How does the frontend receive streaming tutor answers?**
A: `sendChatMessageStream` is an async generator over `fetch` + `ReadableStream`
(`body.getReader()` + `TextDecoder`), parsing `data:` SSE frames. We avoid
`EventSource` because it can't POST or set auth headers easily. On the backend
(P6.1) the answer node calls `llm.astream(...)` and the endpoint drives the
graph with `graph.astream_events(version="v2")`, forwarding the
`on_chat_model_stream` events from the answer node — so the UI renders **real
tokens as they're generated**, not a replay. (Pre-P6.1 this was simulated: the
whole answer was computed then replayed in 24-char word-aware chunks.)

**Q: What are design tokens and why do they matter?**
A: Centralized style values in `index.css` (`nb` parchment background, `nt` ink
ramp, `np` accent, type-scale from `text-3xs` to `text-44`, `text-hero`). They
make theming two whole themes ("Drafting Vellum" light + "Blueprint at Night"
dark) possible by redefining one block, and they keep components free of magic
numbers.

### Micro-SaaS / Webhooks

**Q: How do you secure and dedupe payment webhooks?**
A: Two gates. **Signature verification** — HMAC-SHA256 of the raw body against
`X-Signature` using `LEMONSQUEEZY_WEBHOOK_SECRET`, now **fail-closed**: an unset
secret rejects (503), a mismatch is a 401 (P0). Then **idempotency**: key each
event by its `data.id` / webhook id / stable SHA-256 body hash, store it in
`webhook_events`, and skip any event already processed — so Lemon Squeezy
retries never double-apply a subscription.

**Q: How does billing state reach your database?**
A: Webhooks, not polling. `subscription_created` / `subscription_updated` set
status, tier, quota, and Lemon Squeezy ids on the user's `Subscription`;
`subscription_cancelled` flips status to `cancelled`. Tier mapping uses an exact
`PLAN_TIER_BY_VARIANT` table (P0 — not a spoofable `"pro" in variant_name`
substring); quotas 1500 (Pro) / 300 (Starter) minutes.

**Q: How do you meter LLM spend per user?**
A: Three layers. **Usage metering** — `backend/usage.py:record_pipeline_outcome`
increments `Subscription.used_minutes_this_month`, writes a `UsageLog` row with
per-stage input/output tokens + `estimated_cost_usd`, and persists
`Lecture.duration_seconds`/`status` (P2). **Quota enforcement (pre-spend)** —
`POST /process` requires auth (401), returns 429 when `used >= quota`, over the
free-trial duration cap, or when `used + needed > quota`, all *before* any
Gemini spend. **Observability** — `tutor/llm.py` writes each chat LLM call's
token usage to `outputs/llm_calls.jsonl` (P5.1), and the pipeline self-calibrates
its `POST /estimate` from recorded metrics (P1.8).

### Auth & Security

**Q: Explain the structure of a JWT.**
A: Three base64url segments: header (`alg`, `kid`), payload (claims like `sub`,
`aud`, `exp`, `email`), and signature. The signature proves the token wasn't
modified since signing. I decode it with `pyjwt.decode(token, key,
algorithms=[alg], audience=[...])`.

**Q: HS256 vs ES256 — which does Supabase use and why does it matter?**
A: HS256 is symmetric (one shared secret, `SUPABASE_JWT_SECRET`). ES256 is
asymmetric: Supabase signs with a private key, I verify with a public key from
their JWKS endpoint. Newer Supabase projects default to ES256. If your code only
supports HS256, every token fails to verify — so my `auth.py` inspects the token
header's `alg` and picks JWKS keys for ES256 or the shared secret for HS256.

**Q: What is JWKS and why use it instead of a shared secret?**
A: A JWKS endpoint publishes public keys that clients can fetch to verify JWTs.
It removes the need to share a secret and supports automatic key rotation: keys
carry a `kid`, and `PyJWKClient` caches keys by `kid`, so when Supabase rotates
keys a new `kid` is used automatically without code changes.

**Q: How do you verify a Supabase JWT in a FastAPI backend?**
A: Extract the Bearer token with `HTTPBearer`, read its unverified header for
`alg`, then `pyjwt.decode` with the right key — JWKS public key for ES256, the
`SUPABASE_JWT_SECRET` for HS256. I validate the `aud` is `authenticated`/`anon`
and require `sub`. Any failure returns `None`, and the endpoint decides whether
that's allowed (optional auth) or a 401 (required auth).

**Q: What does "fail closed" mean in this context?**
A: On any verification error — bad signature, expired token, wrong audience,
missing `sub` — the request is treated as unauthenticated. We never silently
accept. The only way around it is an explicit `NORAI_DEV_INSECURE_AUTH=1`
escape hatch that is strictly for local dev and never in production.

**Q: Why is the `aud` claim important?**
A: It restricts which tokens the API accepts. Supabase issues `authenticated`
tokens to real sessions. Checking it prevents token-confusion — e.g. a
Service-Role or `anon` token being replayed against endpoints that require a
signed-in user. We whitelist both `authenticated` and `anon` because guest
sessions use the former.

**Q: How do you protect the anon key vs the service_role key?**
A: The anon key is public by design (baked into the client bundle) — real
security comes from RLS policies and server-side JWT verification. The
service_role key is admin-level and must stay server-side only, never in the
frontend or committed.

**Q: What's a refresh token and why do we never see it?**
A: Access tokens last ~1 hour; refresh tokens are long-lived and used by
supabase-js to silently mint new access tokens when one expires. This keeps the
user logged in. Our backend only verifies access tokens; the refresh token stays
in the browser and localStorage (handled by supabase-js).

### Supabase

**Q: What is Supabase and what did we actually use from it?**
A: A hosted Postgres DB with managed Auth on top. We used Auth (JWTs, email +
anonymous + Google providers) and the raw Postgres database (via
`DATABASE_URL` + asyncpg). We did NOT use the supabase-js data layer — the
Python backend owns the DB.

**Q: Explain anonymous auth. What's required for it to work?**
A: `signInAnonymously()` creates an instant session tied to the browser with a
real JWT (`is_anonymous=true`). Two requirements: the Anonymous provider must be
**enabled in the dashboard**, and the backend must map anonymous users into the
`users` table (we synthesize `<id>@anonymous.norai` emails). It's how a visitor
gets a free 15-minute trial without signing up.

**Q: Why did sign-up show "check your inbox" instead of logging in?**
A: Supabase projects default to requiring email confirmation. `signUp` returns
no session until the user clicks the confirmation link. The UI must handle both
cases: session present (auto-login) vs absent (show confirm notice). When we
tested with a blocked domain (`example.com`), Supabase rejected the address —
which is expected behavior worth knowing.

**Q: What happens to the Google OAuth button if the provider isn't enabled?**
A: The redirect returns an error (redirect URI not allowed / provider disabled).
The provider must be enabled in Authentication → Providers and the callback URL
(e.g. `http://localhost:5173/**`) whitelisted. We wired the button but deferred
enabling it.

**Q: How do sessions persist across browser reloads?**
A: supabase-js stores the session in localStorage. On app start we call
`getSession()` to rehydrate the Zustand store, then subscribe to
`onAuthStateChange` for live updates (login, logout, token refresh). Without the
rehydration call, a reload would appear to log the user out.

### Postgres & SQLAlchemy

**Q: Why async SQLAlchemy and what's the session lifecycle?**
A: Async because the FastAPI server is async — blocking calls would stall the
event loop. `create_async_engine` + `async_sessionmaker` create sessions;
`get_db` yields one per request, commits on success, rolls back on exception,
and always closes. `expire_on_commit=False` means ORM objects stay usable after
commit.

**Q: How did you evolve from `create_all` to Alembic migrations?**
A: `create_all` only creates missing tables — it can't alter existing ones. It
was fine for greenfield dev, but the moment the schema changed (P4.1 added the
job-queue columns to `lectures`) we introduced **Alembic**: `backend/db/migrate.py`
runs `alembic upgrade head` on every startup (idempotent), with
`migrations/versions/0001_initial_schema`, `0002_lecture_pipeline_job_columns`,
`0003_usage_log_columns`, and `0004_courses_and_shares` (P6.4/6.5).
The migration also absorbs pre-Alembic DBs created by `create_all`. Now schema
changes are versioned, ordered, and reversible — and `test_migrations.py`
covers fresh-create + legacy-upgrade. This is a great "when did you outgrow
scaffolding" answer.

**Q: Explain the `postgresql://` → `postgresql+asyncpg://` driver swap.**
A: Async SQLAlchemy engines need an async driver; `psycopg2` is sync and would
block. We rewrite the URL scheme so SQLAlchemy uses `asyncpg`. Pure convenience,
one line, and it keeps the `.env` URL readable.

**Q: Why cascade deletes on all relationships?**
A: GDPR-style data hygiene: when a user is deleted, their subscriptions,
lectures, and usage logs go too — no orphan rows. `ondelete="CASCADE"` at the DB
level plus SQLAlchemy `cascade="all, delete-orphan"` at the ORM level.

**Q: Why use Supabase's user `sub` id as our `users.id` primary key?**
A: So we never have to map between two id systems. The JWT `sub` *is* the user's
identity, so `get_or_create_user_from_token` can upsert directly by it. Single
source of truth, no join gymnastics.

**Q: What is the Session pooler and why did we need it?**
A: Supabase's direct DB host is IPv6-only on this network (no route), causing
connection timeouts. The Session pooler endpoint is IPv4-reachable and also
handles many concurrent connections via pooling. Rule of thumb: use the pooler
unless you have a reason not to.

### Frontend / React

**Q: Why is the auth store a Zustand module singleton?**
A: So it's importable from non-React code like `authHeaders.ts`
(`useAuthStore.getState().token`) — you can read state without a component.
Zustand is lightweight, needs no provider, and the `onAuthStateChange`
subscription keeps the store in sync with Supabase.

**Q: How do you attach auth to streaming requests?**
A: `sendChatMessageStream` adds `Authorization: Bearer <token>` to the fetch
just like a normal POST; the stream itself is a regular `fetch` with
`body.getReader()` + `TextDecoder` parsing `data:` SSE lines. Auth headers are
orthogonal to streaming.

**Q: What does `envDir: '..'` do and why can't the browser see `DATABASE_URL`?**
A: It points Vite at the repo-root `.env`. Vite only exposes `VITE_`-prefixed
vars to the client via `import.meta.env`. Server-only secrets like
`DATABASE_URL` and `SUPABASE_JWT_SECRET` never reach the browser bundle.

**Q: Why use a Vite dev proxy instead of CORS?**
A: The proxy forwards `/chat`, `/quota`, etc. to `localhost:8000` from the
browser's origin, avoiding CORS entirely in dev and allowing relative URLs. CORS
in the backend stays broad for flexibility; the proxy is the primary dev path.

**Q: What is rehydration and why does the app need it?**
A: Auth state is held in memory (Zustand), but the Supabase session survives in
localStorage. On reload, memory is empty, so `getSession()` re-reads the
persisted session and rehydrates the store. Without it, a refresh would look
like a logout.

### Print / PDF

**Q: How did we generate PDFs without a PDF library?**
A: A dedicated print route (`/print?type=…`) renders the document, waits for
data with a 3s timer, then calls `window.print()` — the browser's native dialog
offers "Save as PDF". No extra dependency; pixel-perfect CSS.

**Q: How do you control where pages break in print CSS?**
A: `break-inside: avoid` keeps blocks intact, `break-after: avoid` keeps
headings glued to following content, and `break-before: page` forces new pages
for page-per-chapter layouts. `@media print` scopes these rules to printing.

**Q: Continuous-flow vs page-per-chapter — why both?**
A: Different reading intents. Notes/assessment are studied page-by-page (each
chapter starts fresh); revision/guide reads like a continuous document. A
`continuous` prop on the chapter component switches behavior.

**Q: Why render the mind map as static SVG for print?**
A: The interactive canvas doesn't survive print. We reuse the same layout code
(`conceptMapLayout.ts`) to emit vector SVG — crisp at any zoom, tiny, and
guaranteed to match what the user sees on screen. For an interactive offline
version we separately export a self-contained HTML file.

### System / Ops

**Q: How do you test the backend without a test framework and without paid API calls?**
A: Standalone `test_*.py` scripts (no pytest) run directly:
`scripts/run-tests.sh` executes every offline `test_*.py` and excludes the
live-server probe (`backend/test_api_contract.py`) and `*_probe.py` real-API
scripts. Notable suites: `test_billing_quota.py`, `test_usage.py`,
`test_webhooks.py`, `test_upload_validation.py`, `test_migrations.py`,
`test_jobs_restart.py` (P4 restart-survival), plus the offline contract test
`backend/test_api_contract_offline.py` (P5.8, boots the app in-process with
lifespan startup + Alembic on a temp SQLite DB, 15 checks) and the tutor tests
(`test_hybrid.py`, `test_citations.py`, `test_async_persistence.py`,
`test_evals.py`). Frontend uses **Vitest 4 + React Testing Library** (`npm run
test`, 38 tests) typechecked by the same strict `tsc -b`. CI runs all of it on
every push (P5.3).

**Q: How do you test auth end-to-end without real users?**
A: Anonymous sign-in gives you a real JWT through the actual production flow;
the backend still runs `get_or_create_user_from_token`, so you validate the
whole chain (sign-in → store → header → JWKS verify → DB row). Plus
`test_auth_email.py` covers the token→user mapping deterministically offline.

**Q: What did IPv6 teach you?**
A: Infrastructure connectivity is environment-specific: the "standard" host
(`db.<ref>.supabase.co`) was IPv6-only and unreachable here, while the pooler
worked. Always verify reachability from your actual environment before assuming
config is correct.

**Q: How is the LLM-spend metered?**
A: `backend/usage.py` meters minutes + writes `UsageLog` rows; `/quota` + the
pre-spend 429 gates on `POST /process` enforce the free-trial → starter/pro
funnel; `tutor/llm.py` logs per-call tokens; and the estimator self-calibrates
`POST /estimate` from real metrics.

**Q: How does the app survive a pipeline crash or server restart? (P4)**
A: Jobs are DB rows, not threads. On boot the supervisor `_recover_stale_once`
re-scans `processing` lectures: a stale heartbeat re-queues the job
(`attempts+1`) up to `PIPELINE_MAX_ATTEMPTS`, beyond which it's marked `failed`;
healthy jobs are left alone. Re-claimed jobs resume in the worker pool and —
because every pipeline stage is cache-first (P1.4) — the resume costs ~0 Gemini
calls. This restart-survival story is validated by `backend/test_jobs_restart.py`.

**Q: How do you deploy today? (P5.4)**
A: One container. The multi-stage `Dockerfile` builds the React SPA with
node:20-alpine, then a python:3.12-slim stage installs pinned deps + ffmpeg and
runs FastAPI, which **serves the built SPA** when `frontend/dist` exists
(`NORAI_SPA_DIST`, text/html → `index.html`; API routes unaffected).
`docker compose up` maps 8000, injects the repo-root `.env`, and mounts a
`norai_outputs` volume. Key gotcha: both the lockfile and the container need
`frontend/.npmrc` (`legacy-peer-deps=true`) or `npm ci` fails on the
openapi-typescript/TS peer conflict — a real dependency-reproducibility lesson.
