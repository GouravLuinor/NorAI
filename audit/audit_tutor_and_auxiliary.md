# Part 5 — LangGraph Subsystem, RAG/Vector Search, Auxiliary Pipelines & Frontend Audit

> **Resolution status (updated Aug 2026):** most findings below have since been
> fixed by the P1/P3/P5 hardening passes. **Resolved:** 1.1 (graph re-sequenced
> so `rewrite_query` runs before the text/image retrieval split — enforced by
> `tutor/test_graph_topology.py`), 1.2 (`rewrite_query_node` now clears
> `retrieved_images` alongside `retrieved_chunks`), 2.1 (per-lecture retriever
> client caching), 2.3 (`CONFIDENCE_THRESHOLD` is now 0.35 with strong/weak
> confidence tags, P3.7), 3.2 (adaptive chunking supersedes the fixed
> `DEFAULT_SEGMENTS_PER_CHUNK`, P1.8), 4.1 (lecture-switch flush verified).
> **Superseded by design:** 3.2's "one segment count" concern is moot under
> adaptive chunking. 1.3 (`start_normal`) remains as the conditional routing
> node — harmless. Read the original analysis below as historical context; see
> `tutor/test_*.py` + `backend/test_*.py` for the verification suites.

This is Part 5 of the comprehensive NorAI codebase audit. It provides a deep, line-by-line review of the AI Tutor subsystem (`tutor/`), vector search & retrieval pipelines (`retriever.py`, `embedding.py`), auxiliary pipeline compilers (`chapter_builder.py`, `chunk.py`), and frontend state synchronization (`useThreadStore.ts`).

---

## 1. LangGraph Subsystem & State Graph Topology (`tutor/graph.py`, `tutor/state.py`)

### 1.1 Parallel Branch Race Condition (`start_normal` Node)
In [tutor/graph.py:L84-L88](file:///home/gourav/coding/VScode/Projects/NorAI/tutor/graph.py#L84-L88):
```python
builder.add_edge("start_normal", "retrieve_images")
builder.add_edge("start_normal", "rewrite_query")
builder.add_edge("rewrite_query", "retrieve")
builder.add_edge("retrieve", "generate_answer")
builder.add_edge("retrieve_images", "generate_answer")
```

- **Bug Description**: `start_normal` branches concurrently into `retrieve_images` and `rewrite_query`. `rewrite_query` is the node responsible for generating `search_query` from the user's question and conversation history. Because `retrieve_images` executes in parallel with `rewrite_query`, `retrieve_images_node` evaluates `state.get("search_query")` *before* `rewrite_query_node` finishes writing it.
- **Impact**: Image retrieval (`retrieve_images`) is strictly executed using the un-rewritten raw `user_question` or a stale `search_query` from the *previous* turn. If a user asks a follow-up question like *"Can you show me the diagram for that?"*, `rewrite_query` resolves *"that"* to *"Linear Regression graph"*, but `retrieve_images` queries Chroma using the raw string *"Can you show me the diagram for that?"*, failing to retrieve relevant screenshots.
- **Remediation**: Re-sequence the graph topology so `rewrite_query` runs *before* splitting into text and image retrieval branches:
  ```python
  builder.add_edge("start_normal", "rewrite_query")
  builder.add_edge("rewrite_query", "retrieve")
  builder.add_edge("rewrite_query", "retrieve_images")
  builder.add_edge("retrieve", "generate_answer")
  builder.add_edge("retrieve_images", "generate_answer")
  ```

---

### 1.2 Stale `retrieved_images` State Retention
In [tutor/nodes_retrieval.py:L177](file:///home/gourav/coding/VScode/Projects/NorAI/tutor/nodes_retrieval.py#L177) and [tutor/nodes_retrieval.py:L190](file:///home/gourav/coding/VScode/Projects/NorAI/tutor/nodes_retrieval.py#L190):

- **Bug Description**: `rewrite_query_node` explicitly clears stale text chunks on every turn by returning `{"search_query": rewritten, "retrieved_chunks": []}`. However, `retrieve_images_node` does not have a clearing step at the start of the turn.
- **Impact**: If image retrieval for a new question fails, encounters an exception, or returns 0 images, `retrieved_images` from the *previous* conversation turn persists in `ChatState`. `generate_answer_node` then reads the old `retrieved_images` and injects irrelevant screenshot captions into the current prompt turn.
- **Remediation**: Explicitly clear `retrieved_images` in `rewrite_query_node`:
  ```python
  return {"search_query": rewritten, "retrieved_chunks": [], "retrieved_images": []}
  ```

---

### 1.3 Redundant Topology Node (`start_normal`)
In [tutor/graph.py:L31](file:///home/gourav/coding/VScode/Projects/NorAI/tutor/graph.py#L31):
```python
builder.add_node("start_normal", lambda state, config: {})
```
- **Finding**: `start_normal` is a dummy pass-through node used purely as an edge routing target after `detect_chapter`. Routing `detect_chapter` directly to `rewrite_query` eliminates an unnecessary graph state transition tick.

---

## 2. Vector Search & RAG Quality (`tutor/retriever.py`, `tutor/embedding.py`, `tutor/retrieval_config.py`)

### 2.1 Direct Chroma Client Re-Initialization in `retrieve_images_node`
In [tutor/nodes_retrieval.py:L144-L148](file:///home/gourav/coding/VScode/Projects/NorAI/tutor/nodes_retrieval.py#L144-L148):
```python
client = chromadb.PersistentClient(path=str(chroma_dir))
embedding_fn = GeminiEmbeddingFunction(role="query")
```
- **Finding**: While [tutor/retriever.py:L57-L87](file:///home/gourav/coding/VScode/Projects/NorAI/tutor/retriever.py#L57-L87) defines process-wide singleton functions (`_get_client()`, `_get_notes_collection()`) using `@lru_cache`, `retrieve_images_node` in `nodes_retrieval.py` bypasses `retriever.py` and creates a brand-new `chromadb.PersistentClient` and `GeminiEmbeddingFunction` instance on every single user message.
- **Impact**: Re-creating the Chroma persistent client on every message causes unnecessary disk lock acquisition and doubles Google GenAI API client initialization latency.
- **Remediation**: Update `retrieve_images_node` to call `retrieve_images()` from `tutor.retriever` directly.

---

### 2.2 Asymmetric Prompt Formatting in `GeminiEmbeddingFunction`
In [tutor/embedding.py:L101-L115](file:///home/gourav/coding/VScode/Projects/NorAI/tutor/embedding.py#L101-L115):
```python
def _format_document(self, text: str, title: str | None = None) -> str:
    t = title if title else "none"
    return f"title: {t} | text: {text}"

def _format_query(self, text: str) -> str:
    return f"task: question answering | query: {text}"
```
- **Finding**: `GeminiEmbeddingFunction` correctly implements asymmetric text formatting for `gemini-embedding-2` per Google AI documentation.
- **Observation**: During index creation ([tutor/build_index.py](file:///home/gourav/coding/VScode/Projects/NorAI/tutor/build_index.py)), passing `title` (e.g. `title: "Chapter 4: Support Vector Machines"`) enhances vector clustering. Ensure `build_index.py` passes chapter titles into `_format_document`.

---

### 2.3 Confidence Threshold Tuning (`CONFIDENCE_THRESHOLD = 0.30`)
In [tutor/retrieval_config.py:L48](file:///home/gourav/coding/VScode/Projects/NorAI/tutor/retrieval_config.py#L48):
```python
CONFIDENCE_THRESHOLD = 0.30
```
- **Finding**: In `generate_answer_node` ([tutor/nodes.py:L166-L170](file:///home/gourav/coding/VScode/Projects/NorAI/tutor/nodes.py#L166-L170)), if all retrieved chunks have a cosine distance $> 0.30$, `_build_low_confidence_context_block` is used to append a low-confidence warning.
- **Evaluation**: For dense mathematical or technical notes embedded with `gemini-embedding-2` (768 dimensions), highly relevant technical passages often yield cosine distances between `0.24` and `0.33`. Setting `CONFIDENCE_THRESHOLD = 0.30` can occasionally trigger false-alarm low-confidence disclaimers on valid technical matches.
- **Recommendation**: Relax `CONFIDENCE_THRESHOLD` slightly to `0.35` to avoid false disclaimers on technical queries.

---

## 3. Auxiliary Pipeline Compilers (`notes/chapter_builder.py`, `chunking/chunk.py`)

### 3.1 Un-Deduplicated Merged Arrays in `chapter_builder.py`
In [notes/chapter_builder.py:L178-L300](file:///home/gourav/coding/VScode/Projects/NorAI/notes/chapter_builder.py#L178-L300):
- **Finding**: `build_chapters()` aggregates merged chunk arrays (`focus_concepts`, `topics`, `concepts`, `screenshots`) using `extend()`.
- **Issue**: If multiple chunks in the same chapter list identical concepts or screenshots, `chapter_N.json` contains duplicate array entries.
- **Fix**: Apply order-preserving list deduplication (`dict.fromkeys(...)`) when compiling `Chapter` arrays:
  ```python
  chapter_data["focus_concepts"] = list(dict.fromkeys(chapter_data["focus_concepts"]))
  ```

---

### 3.2 Fixed Segment Chunking (`DEFAULT_SEGMENTS_PER_CHUNK = 15`)
In [chunking/chunk.py:L15](file:///home/gourav/coding/VScode/Projects/NorAI/chunking/chunk.py#L15):
- **Finding**: Transcript chunking groups segments in fixed 15-segment batches ($\approx 50$–$80$ seconds).
- **Evaluation**: Fixed segment counts are robust and fast. With Tier 0's mapping fallback and Tier 1's structured output enabled, fixed segment chunking is completely reliable for downstream stages.

---

## 4. Frontend Integration & State Sync (`frontend/src/stores/useThreadStore.ts`)

### 4.1 Local Storage Key Scope Isolation
In [frontend/src/stores/useThreadStore.ts:L78-L103](file:///home/gourav/coding/VScode/Projects/NorAI/frontend/src/stores/useThreadStore.ts#L78-L103):
- **Finding**: `useThreadStore.ts` correctly partitions thread storage per active lecture using `${THREADS_KEY}-${lectureId}`.
- **Optimization**: When switching active lectures, ensure `useThreadStore.getState().reset()` or `loadThreads()` is called to flush active state and prevent stale thread messages from briefly displaying.

---

## Summary of Recommended Action Items (Part 5)

1. **Re-sequence LangGraph Retrieval Branches**: Move `rewrite_query` before `retrieve_images` in `tutor/graph.py` so image retrieval uses the rewritten query.
2. **Clear `retrieved_images` per Turn**: Reset `retrieved_images: []` in `rewrite_query_node`.
3. **Use Singleton Retriever**: Replace direct `chromadb.PersistentClient` instantiation in `retrieve_images_node` with `tutor.retriever.retrieve_images()`.
4. **Deduplicate Chapter Builder Arrays**: Apply `list(dict.fromkeys(...))` in `chapter_builder.py`.
5. **Adjust Confidence Threshold**: Update `CONFIDENCE_THRESHOLD = 0.35` in `tutor/retrieval_config.py`.
