# NorAI — Full-Project Tutorial & Interview Prep

Everything built in this project — from the 18-stage pipeline and RAG tutor to
the Supabase auth and PDF exports — the concepts behind it, what you should know
as a developer, and the questions interviewers are likely to ask, with full
answers.

The project is ordered **oldest → newest**, matching the git history. The table
below shows the recent milestone commits (later milestones get full parts; the
earliest skeleton/mock-data commits are folded into the architecture parts).

| Commit | What it did |
|---|---|
| `1805f00` → `…` | Initial skeleton → multi-source ingestion → chunking → RAG → pipeline (Parts 1–2) |
| `5715261` → `3ff9fa4` | Frontend shell, real backend integration, workspace, design-token overhauls (Part 3) |
| `7234c00` | Mind-map (Phase D) concept map, floatable cards & tutor source/reference fixes |
| `5175684` | Production Micro-SaaS foundation — DB schema, auth, webhooks & landing/pricing UI (Part 4) |
| `a12a387` | QA fixes — tutor memory, missed-question correctness, quiz load path & flashcard stats |
| `dacad59` | Wire Supabase end-to-end — Postgres + real auth (Part 5) |
| `e67918b` | Real guide & mind-map PDFs, interactive HTML export, continuous-flow print (Part 6) |
| `f46b949` | Landing/pricing review pass — type-scale tokens, a11y, mobile overflow & copy (Part 7) |

**What you learned in one paragraph:** you built an end-to-end AI platform that
turns lecture videos into structured study material. An **18-stage multimodal
pipeline** (Faster-Whisper transcription + Gemini knowledge extraction + OpenCV
visual analysis) runs in a background thread and emits progress; a **LangGraph +
ChromaDB RAG tutor** retrieves lecture-grounded context and answers
conversationally; a **React workspace** with notes/revision/assessment/flashcards/
mind-map panels polls progress and streams tutor answers over SSE; then you
**productionized** it with Postgres, real Supabase auth (JWT verified via JWKS),
usage metering and Lemon Squeezy webhooks; and finally hardened **PDF exports**
via the browser print pipeline.

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

`backend/orchestrator.py` is **fully synchronous** and runs inside a **daemon
`threading.Thread`** spawned by `POST /process`. Why a thread and not asyncio?

- The pipeline makes long blocking calls (FFmpeg, Faster-Whisper, Gemini HTTP)
  that would stall an async event loop.
- Running it in a dedicated thread keeps the FastAPI server responsive so the
  frontend can poll status.

Inside the thread, two branches run **in parallel** with a
`ThreadPoolExecutor(max_workers=2)`:

```python
def _run_text_branch():    # transcription → chunking → knowledge extraction
def _run_visual_branch():  # frame extraction → scene detection
```

Both branches' `.result()` are awaited before the sequential stages that follow.
This halves wall-clock time for the two expensive, independent parts.

## 1.3 Progress tracking: `TaskProgress` + `asyncio.run_coroutine_threadsafe`

A `TaskProgress` dataclass holds `stage`, `message`, `percent`, `finished`,
`error`, and a list of `asyncio.Queue`s. Updating it is **thread-safe**:

```python
def update_progress_sync(task_id, stage, message, percent):
    tp = get_or_create_task_sync(task_id)
    tp.stage = stage; tp.message = message; tp.percent = percent
    for q in tp._queues:
        asyncio.run_coroutine_threadsafe(q.put({...}), loop)
```

`asyncio.run_coroutine_threadsafe` is how a **synchronous background thread**
pushes work onto an **asyncio event loop** (a separate, lazily created one via
`_get_event_loop`). The status endpoint reads the dict directly with a lock.

> **Gotcha worth knowing for interviews:** the SSE push queues are defined but
> **no endpoint ever registers a queue** — the frontend actually **polls**
> `GET /process/{task_id}/status` every 1.5s. The push infra is scaffolding; the
> real transport is polling. The only true SSE stream in the app is
> `POST /chat/stream` (Part 2.9).

## 1.4 Stage-by-stage (the actual order in the code)

| # | Progress stage | What happens | Engine |
|---|---|---|---|
| 1 | `ingestion` | `process_source` routes YouTube (`yt-dlp`) / Google Drive (`gdown`) / upload; extracts MP3 via FFmpeg; writes `videos/`, `audio/`, `metadata/` | Local tools |
| 2 | `transcription` | **Faster-Whisper** (`base` model, CPU int8) → timestamped `transcripts/*.json` | Local |
| 3 | `chunking` | groups ~5 transcript segments into context-preserving chunks → `chunks/*_chunks.json` | Local |
| 4 | `knowledge_extraction` | per-chunk **Gemini** structured `KnowledgeObject` (topic, notes, key points, concepts) with retries + rate limiter | Gemini |
| 5 | `frame_extraction` | samples frames every 8s via OpenCV → `screenshots/raw` | Local |
| 6 | `scene_detection` | pixel-diff threshold dedup → keyframes | Local |
| 7 | `mapping` | associates keyframes to transcript chunks by timestamp → `mappings/chunk_screenshot_mapping.json` | Local |
| 8 | `outline` | LLM infers title + 3–6 chapters, renumbers `chapter_id`s, assigns chunk ranges | Gemini |
| 9 | `visual_knowledge` | **Gemini multimodal** reads chapter-batched keyframe images → `visual_objects/` | Gemini |
| 10 | `knowledge_merging` | fuses text + visual objects → `merged_objects/` | Local |
| 11 | `chapter_building` | aggregates merged objects into Pydantic `Chapter`s (no LLM) → `chapters/chapter_N.json` | Local |
| 12 | `screenshot_selection` | two-pass: quality scoring (Gemini) → perceptual-hash dedup → top-K ranking → `screenshots/selected/` | Gemini + local |
| 13 | `chapter_artifacts` | **one Gemini call per chapter** → study notes + revision + assessment + flashcards (`MergedChapterArtifactsModel`) | Gemini |
| 14 | `tutor_index` | chunks `notes/chapter_*.md`, embeds into per-lecture Chroma `norai_notes` | Chroma + Gemini embed |
| 15 | `screenshot_index` | indexes screenshot captions into `screenshot_captions` collection | Chroma + Gemini embed |
| 16 | `cleanup` | deletes intermediates (videos/audio/raw/chunks/objects…) if final artifacts exist | Local |

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
monetization story (Part 4).

## 1.7 Lecture isolation & the registry

`backend/lecture_registry.py` maintains a file-backed JSON registry
(`outputs/lectures.json`) guarded by a `threading.Lock`. `create_lecture`
creates `outputs/{lecture_id}/` with subdirs (`notes/`, `revision/`,
`assessment/`, `screenshots/keyframes/`, `screenshots/selected/`, `flashcards/`,
`pdfs/`, `tutor/`). Every stage writes under this dir, so **artifacts never leak
across lectures**. The `lecture_id` (the `task_id`) is the single identity key
propagated through routes, stores, indexes, and conversations.

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
start_normal → rewrite_query → retrieve + retrieve_images → generate_answer → save_memory → END
```

LangGraph gives you a **stateful, persistent graph**: nodes are functions that
mutate `state`, and the `add_messages` reducer appends to the conversation list.
The compiled graph is bound to a **checkpointer** (SQLite via
`tutor/memory.py`, `SqliteSaver`) so conversation state survives across turns and
process restarts.

## 2.3 Two retrieval indexes

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
  `CONVERSATION SUMMARY:` SystemMessage appended to the transcript.

So the model gets real long-horizon memory without an unbounded prompt.

## 2.7 Query rewriting & chapter detection

- `detect_chapter_node` regex-matches the question for chapter numbers and
  command keywords (`quiz`, `summary`, `flashcards`).
- `rewrite_query_node` has Gemini rewrite the raw question into a
  **self-contained search query** (useful for follow-ups like "what about the
  second one?").
- `commands.py` `execute_command` is a **no-LLM tool runner** that starts a quiz
  or shows a summary/flashcards when a command intent is detected.

## 2.8 Quiz-in-chat

`quiz_nodes.py` adds a self-contained quiz loop to the graph: `quiz_ask` →
`quiz_store_answer` → (repeat) → `quiz_llm_evaluate`, which parses a
`FINAL SCORE: X out of Y` line. So a user can take a 5-question quiz inside the
chat with the same conversation context.

## 2.9 `/chat/stream` — SSE streaming (the real SSE in this app)

`POST /chat/stream` (`backend/main.py`):

1. The **entire answer is computed first** (`invoke_tutor` runs in a background
   thread via `asyncio.to_thread`; LangGraph `graph.invoke` — no true token
   streaming).
2. The finished string is **replayed as SSE in 24-char chunks**, word-boundary
   aware (extends to the next space if within 12 chars), JSON-wrapped as
   `data: {"t": "..."}\n\n`, with a 2ms `asyncio.sleep` between frames so the UI
   renders progressively.
3. Final frame `data: {"final": {...}}` carries `assistant_message_id`,
   `retrieved_chunks`, `retrieved_images`, `chapter_id`, `thread_id`; then
   `data: [DONE]`.

Headers: `media_type="text/event-stream"`, `Cache-Control: no-cache`,
`X-Accel-Buffering: no`.

On the frontend, `sendChatMessageStream` in `lib/chatApi.ts` is an **async
generator**: it reads `res.body.getReader()` + `TextDecoder`, buffers `\n`
frames, skips non-`data:` lines, and yields string chunks or a `{type:'final'}`
object. This is a great example of client-side SSE parsing without
`EventSource` (which can't POST or send auth headers easily).

## 2.10 Threads: two storage layers

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

React 19 + TypeScript + Vite + Tailwind 4 + Zustand 5 + React Router 7 +
framer-motion + react-markdown/KaTeX. Routes in `src/App.tsx`:

| Route | Component |
|---|---|
| `/` | Landing page (marketing) |
| `/pricing` | Pricing page |
| `/app` | Upload page |
| `/process/:taskId` | Pipeline progress |
| `/workspace/:lectureId` | The 3-pane workspace |
| `/print` | Print/PDF route (`?type=…&lecture_id=…`) |

## 3.2 The 3-pane workspace

`Workspace.tsx` renders a CSS grid (`sidebar | doc | ai-panel`) with draggable,
keyboard-accessible resize separators (min/max constants). Escape toggles the
sidebar. The panels:

- **Sidebar** — lecture `<select>`, chapter list, thread list, quota badge,
  theme toggle.
- **DocPanel** — tab bar (Notes / Revision / Assessment / Guide / Mind map),
  search, PDF + interactive-export buttons.
- **AIPanel** — tutor chat / quiz / flashcards, swapped with Framer transitions;
  width adapts between tutor mode (narrow) and quiz/cards mode (wide).

## 3.3 Zustand stores & state propagation

| Store | Purpose |
|---|---|
| `useLectureStore` | active `lectureId`, `lectures[]` |
| `useChapterStore` | active chapter, doc tab, sidebar collapsed |
| `useThreadStore` | threads, messages, streaming text, live references, per-thread cache |
| `useQuizStore` | AI mode, quiz session, answers/confidences, flashcards, ratings |
| `useAuthStore` | Supabase user/token (Part 5) |
| `useTutorSettingsStore` | persona, persisted per-lecture |
| `useToastStore` | toasts |

**State propagation:** `lectureId` comes from the URL → `setActiveLecture` →
`loadChapters(lectureId)`. Every doc/chat/quiz/flashcard component reads the
active lecture (falling back to `'default'`) and the active chapter, then fetches
lecture-scoped API data. `lib/threadStorage.ts:getLectureId()` centralizes this,
scoping both API calls and localStorage keys per lecture.

## 3.4 Progress UI: polling, not SSE

`ProcessingPage.tsx` polls `GET /process/{taskId}/status` every **1.5s** with
`setInterval`. A hardcoded `STAGES` array drives a 16-step "rail"; completed
stages get checkmarks, the active stage pulses, and an animated "ink" line draws
down (framer-motion, respects `prefers-reduced-motion`). On `complete` →
navigate to `/workspace/{taskId}`.

## 3.5 Tutor chat UI

- `ChatArea.tsx`: optimistic user message; streaming via
  `sendChatMessageStream`; the final assistant message commits under the
  **original thread id** even if the user switched threads mid-stream, with an
  atomic dedup guard.
- `MessageBubble.tsx`: user right, assistant left with ReactMarkdown
  (`remark-math` + `rehype-katex`).
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

- Cards rated Again/Hard/Good/Easy, with a **3D flip** via CSS
  (`perspective-1000`, `transform-style-3d`, `rotate-y-180`, `backface-hidden`).
- Ratings persist keyed by **`getCardKey()` — a SHA-256 hash of the normalized
  front text** (`lib/hash.ts`), so they survive reloads even if deck structure
  changes.
- Filter to missed-only; stats footer derives Reviewed/Got it/Almost/Left from
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
  light-edge shadows.
- **Type ramp** from `text-3xs` to `text-44`, plus a `text-hero` serif token.
- Signature decorative CSS: `.bg-blueprint-grid`, `.noise` (paper grain),
  `.fold-marks`, `.spec-label`, `.ripple`, `.scroll-highlight`, and a `@media
  print` block.
- Text-accent utilities (`text-np` etc.) get a tuned `-t` variant for 4.5:1
  contrast while solid fills stay saturated.

## 3.10 Vite dev proxy

`vite.config.ts` proxies ~20 API paths (`/process`, `/chat`, `/quiz`,
`/notes`, `/study-guide`, `/quota`, …) to `localhost:8000`, so the frontend uses
relative URLs and avoids CORS during dev.

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
  header using `LEMONSQUEEZY_WEBHOOK_SECRET` (dev mode accepts anything if the
  secret is unset; 401 on mismatch in production).
- **Idempotency:** event key = `data.id` / `meta.webhook_id` / hash of the body;
  already-processed events return "Event already processed" without re-applying.
- **Tier/quota mapping:** `plan_tier = "pro" if "pro" in variant_name else
  "starter"`; `quota_minutes = 1500` (Pro, 25h) or `300` (Starter, 5h).
- Handles `subscription_created` / `subscription_updated` (sets status, tier,
  quota, Lemon Squeezy ids) and `subscription_cancelled`.

Webhooks are how external billing events become DB state — no polling of the
payment provider.

## 4.3 Usage metering & quota enforcement

- `usage_logs` record per-stage input/output tokens + `estimated_cost_usd` per
  user/lecture.
- `subscriptions.monthly_minutes_quota` caps lecture minutes;
  `used_minutes_this_month` tracks spend.
- `GET /quota` returns the remaining budget; `POST /process` returns **429** once
  exhausted. This is the free-trial → starter/pro funnel in code.

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

## 5.8 Database wiring (async SQLAlchemy 2.0)

`backend/db/database.py`:

- `load_dotenv()` — makes sure `.env` is loaded even if imported standalone.
- `DATABASE_URL` resolves to env var, else falls back to SQLite for local dev.
- The driver is swapped: `postgresql://` → `postgresql+asyncpg://` because
  SQLAlchemy async engines need an async driver.
- `create_async_engine` + `async_sessionmaker(expire_on_commit=False)`.
- `get_db()` — async generator FastAPI dependency; commits on success,
  rolls back on exception, always closes.
- `init_db()` — `Base.metadata.create_all` creates all 5 tables.

**Why `create_all` and not Alembic?** `create_all` only *creates* missing
tables; it can't alter existing ones. Fine for early-stage/throwaway dev, but in
production you'd migrate with Alembic (see interview Q below).

## 5.9 The schema (`models.py`)

5 tables with FK relationships and cascade deletes:

```
users 1──1 subscriptions      (user_id unique, cascade delete)
users 1──N lectures           (cascade delete)
users 1──N usage_logs         (cascade delete)
lectures 1──N usage_logs      (cascade delete)
webhook_events                (idempotency key = Lemon Squeezy event id)
```

- `User.subscription` is `uselist=False` (one-to-one).
- Foreign keys use `ondelete="CASCADE"` so deleting a user cleans up all their
  data — required by data-privacy law and plain good hygiene.
- `usage_logs` store per-stage token counts + `estimated_cost_usd` — used to
  meter real LLM spend per user.

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
| **`asyncio.run_coroutine_threadsafe`** | Push work from a sync thread onto an event loop |
| **SSE** | Server-Sent Events — one-way server→client stream (`data:` frames) |
| **Polling** | Client repeatedly fetches status instead of receiving pushes |
| **RAG** | Retrieval-Augmented Generation — retrieve context, then generate |
| **Vector store** | DB that searches by embedding similarity (ChromaDB) |
| **Embedding** | Dense numeric vector representing text meaning |
| **Asymmetric embedding** | Documents and queries formatted differently before embedding |
| **LangGraph** | Framework for stateful LLM graphs with checkpoints |
| **Checkpointer** | Persists graph state so conversations survive restarts |
| **Structured output** | LLM forced into a Pydantic/schema shape; validate + retry |
| **Perceptual hash (pHash)** | Image fingerprint for near-duplicate detection |
| **Webhook** | Provider calls your URL on an event; no polling |
| **HMAC-SHA256** | Keyed message signature used to verify webhook origin |
| **Idempotency** | Same event processed once even if delivered repeatedly |
| **Usage metering** | Recording tokens/cost per user for billing |
| **Design tokens** | Centralized style values (colors/spacing/type) in CSS |
| **Type-scale** | Deliberate, ordered set of font sizes |
| **Zustand** | Tiny React state store with `getState()` outside components |
| **Optimistic update** | Show the change before the server confirms |

---

## Developer Cheat-Sheet

**Commands** (from repo root):

```bash
./scripts/start-dev.sh {start|stop|status}   # backend :8000 + frontend :5173
venv/bin/python -m uvicorn backend.main:app --reload --port 8000   # backend alone
cd frontend && npm run dev                   # vite :5173
cd frontend && npm run lint                  # oxlint
cd frontend && npm run build                 # tsc -b && vite build
venv/bin/python tutor/test_chunker.py        # standalone test scripts (no pytest)
```

**Gotchas to remember:**

- Launch backend with `-m` from repo root (needs `config.py` importable).
- Health-check via HTTP probe, not log-file size.
- Never relaunch over an occupied port (uvicorn spins at 120% CPU).
- **All pipeline stages cost Gemini tokens — don't run the pipeline casually.**
- The free-trial gate blocks lectures > 15 min (`MAX_FREE_DURATION_MIN`).
- Most pipeline stages tolerate failure — check `outputs/<id>/backend.log`.
- `.env` (repo root) holds secrets: `DATABASE_URL`, `SUPABASE_JWT_SECRET`,
  `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`. Never commit it.
- Anonymous + email providers must be enabled in the Supabase dashboard.
- `outputs/` and `.tmp/` are throwaway — never commit.

**Key file map:**

- `backend/orchestrator.py` — pipeline runner + progress
- `backend/lecture_registry.py` — lecture dirs/registry
- `backend/auth.py` — JWT verification + auth dependencies
- `backend/db/database.py` — async engine + session + `init_db()`
- `backend/db/models.py` — 5-table schema
- `backend/routers/webhooks.py` — Lemon Squeezy billing events
- `tutor/graph.py`, `tutor/nodes.py`, `tutor/retriever.py`, `tutor/embedding.py` — RAG tutor
- `frontend/src/stores/*` — Zustand stores (auth, lecture, chapter, thread, quiz)
- `frontend/src/lib/supabaseClient.ts` — supabase-js client
- `frontend/src/lib/authHeaders.ts` — Bearer injection
- `frontend/vite.config.ts` — `envDir: '..'` + proxy
- `frontend/src/components/PrintPage.tsx` — print/PDF route

---

## Interview Prep — Q&A

### Pipeline & Async

**Q: How did you run a long AI pipeline without blocking the API server?**
A: `POST /process` spawns a **daemon `threading.Thread`** that runs the fully
synchronous pipeline (`run_pipeline`). FastAPI stays responsive, and the
frontend polls status. Inside, the two independent branches — text (transcribe →
chunk → extract) and visual (frames → scenes) — run in parallel with a
`ThreadPoolExecutor(max_workers=2)`.

**Q: Why a background thread instead of an async task?**
A: The pipeline makes long blocking calls (FFmpeg, Faster-Whisper, Gemini HTTP).
Running those on the event loop would block every other request. A dedicated
thread keeps the server responsive. Blocking LLM calls in request handlers are
similarly offloaded with `asyncio.to_thread`.

**Q: How does progress get from a sync thread to the frontend?**
A: A `TaskProgress` dict is mutated under a `threading.Lock`. To push updates to
asyncio consumers, the thread uses `asyncio.run_coroutine_threadsafe(q.put(...),
loop)` on a lazily created event loop. In practice, the frontend **polls**
`GET /process/{id}/status` every 1.5s — the push queues are scaffolding that no
endpoint actually registers. Worth being honest about in an interview: I built
the push primitive but shipped polling.

**Q: How did you make the pipeline resilient to failures?**
A: **Partial-failure tolerance.** Only hard-dependency stages (ingestion,
duration check, the two parallel branches) fail the run. Everything from mapping
onward is wrapped in try/except that logs and continues; outline generation even
writes a single-chapter fallback on failure. A bad optional stage never discards
the successful work already produced.

**Q: What does the 15-minute free-trial gate do?**
A: After ingestion it reads the video duration from metadata and raises if it
exceeds `MAX_FREE_DURATION_MIN` while `ENFORCE_FREE_TRIAL_DURATION=true`. It's
the first line of the monetization funnel, enforced in the pipeline itself.

**Q: Why one LLM call per chapter instead of one per artifact?**
A: Cost. `generate_consolidated_chapter_artifacts` makes a single Gemini call
per chapter with `response_schema=MergedChapterArtifactsModel` returning notes
sections + revision summary + assessment questions (with embedded flashcard
fields). Four artifact types, one paid call. Flashcards are then a pure
transform — zero extra LLM calls.

### RAG & Embeddings

**Q: Walk me through the RAG flow.**
A: `load_memory` rebuilds the prompt window → `detect_chapter` scopes to the
chapter → `rewrite_query` makes the question self-contained → `retrieve` +
`retrieve_images` query the per-lecture Chroma indexes (filtered by
`chapter_id`) → `generate_answer` injects the results as CONTEXT SystemMessages
into a Gemini prompt → `save_memory` summarizes when history grows. Grounded in
the lecture, not the model's general knowledge.

**Q: Why did you write a custom Chroma embedding function?**
A: The built-in Chroma wrapper only documents `gemini-embedding-001` and passes a
`task_type=` parameter, but **`gemini-embedding-2` removed `task_type`** — task
instructions go in the prompt text instead. My `GeminiEmbeddingFunction` formats
documents as `"title: … | text: …"` and queries as
`"task: question answering | query: …"` (asymmetric), wraps each string in its
own `Content`, and retries with exponential backoff.

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
but the most recent 6 into a `CONVERSATION SUMMARY:` record. This was a real
bug fix — the tutor was previously stateless.

**Q: How do you verify what the model "knows" is actually in the lecture?**
A: We don't trust it blindly. Retrieval is always scoped to the lecture's own
index, and there's a **low-confidence mode**: if every retrieved chunk exceeds a
cosine-distance threshold, the context block tells the model to express
uncertainty instead of hallucinating.

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
`EventSource` because it can't POST or set auth headers easily. The backend
precomputes the whole answer then replays it in 24-char word-aware chunks — it's
simulated streaming, not true token streaming.

**Q: What are design tokens and why do they matter?**
A: Centralized style values in `index.css` (`nb` parchment background, `nt` ink
ramp, `np` accent, type-scale from `text-3xs` to `text-44`, `text-hero`). They
make theming two whole themes ("Drafting Vellum" light + "Blueprint at Night"
dark) possible by redefining one block, and they keep components free of magic
numbers.

### Micro-SaaS / Webhooks

**Q: How do you secure and dedupe payment webhooks?**
A: Verify the HMAC-SHA256 signature of the raw body against `X-Signature` using
the shared secret (401 on mismatch). Then **idempotency**: key each event by its
`data.id` / webhook id / body hash, store it in `webhook_events`, and skip any
event already processed — so Lemon Squeezy retries never double-apply a
subscription.

**Q: How does billing state reach your database?**
A: Webhooks, not polling. `subscription_created` / `subscription_updated` set
status, tier, quota, and Lemon Squeezy ids on the user's `Subscription`;
`subscription_cancelled` flips status to `cancelled`. Tier mapping:
`"pro" if "pro" in variant_name else "starter"`, quotas 1500 / 300 minutes.

**Q: How do you meter LLM spend per user?**
A: `usage_logs` record per-stage input/output tokens and `estimated_cost_usd`.
`subscriptions.monthly_minutes_quota` caps lecture minutes and
`used_minutes_this_month` tracks usage; `/quota` returns the remaining budget and
`POST /process` returns **429** once exhausted.

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

**Q: Why `create_all` instead of Alembic migrations?**
A: `create_all` only creates missing tables — it can't change existing ones.
It's fine for a greenfield/dev stage, but any schema change (adding a column,
altering a constraint) silently won't happen. Production needs Alembic migration
files for versioned, reversible schema changes. This is an interview favorite.

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

**Q: How do you test auth end-to-end without real users?**
A: Anonymous sign-in gives you a real JWT through the actual production flow;
the backend still runs `get_or_create_user_from_token`, so you validate the
whole chain (sign-in → store → header → JWKS verify → DB row).
`test_api_contract.py` covers API shapes; standalone `test_*.py` scripts cover
logic — there's no pytest framework in this repo.

**Q: What did IPv6 teach you?**
A: Infrastructure connectivity is environment-specific: the "standard" host
(`db.<ref>.supabase.co`) was IPv6-only and unreachable here, while the pooler
worked. Always verify reachability from your actual environment before assuming
config is correct.

**Q: How is the LLM-spend metered?**
A: `usage_logs` record per-stage input/output tokens and `estimated_cost_usd`;
`subscriptions.monthly_minutes_quota` caps lecture minutes; `/quota` returns the
remaining budget and the process route blocks once exhausted. It's the basis for
the free-trial → starter/pro upgrade funnel.
