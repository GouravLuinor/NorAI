"""
backend/dependencies.py (P4.4 — async tutor persistence)

Provides the NorAI tutor graph, one instance per lecture, served
asynchronously. Each lecture owns its own AsyncSqliteSaver-backed
checkpointer (stored under outputs/{lecture_id}/tutor/) and a dedicated
asyncio.Lock, so:

  - turns on DIFFERENT lectures run concurrently, and
  - turns on the SAME lecture serialize (one slow Gemini turn never
    blocks chat on other lectures), and
  - the event loop is never blocked by an LLM call (the LLM nodes are
    `async def` and use `llm.ainvoke`).

The per-lecture graph cache is LRU-bounded at config.TUTOR_MAX_CACHED_GRAPHS
so long-lived processes don't leak an unbounded number of sqlite
connections / compiled graphs.
"""

import asyncio
import re
import sqlite3
from collections import OrderedDict
from pathlib import Path

import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from config import CHECKPOINT_DB_PATH, TUTOR_MAX_CACHED_GRAPHS
from tutor.graph import build_graph


# ---------------------------------------------------------------------------
# Per-lecture graph cache (LRU-bounded, P4.4)
# ---------------------------------------------------------------------------

# Global default graph (used when no lecture_id is supplied), built lazily.
_default_graph = None
_default_graph_init_lock = asyncio.Lock()
_default_turn_lock = asyncio.Lock()

# LRU cache: lecture_id -> {"graph": ..., "lock": asyncio.Lock,
#                           "conn": aiosqlite.Connection, "db_path": Path}
_lecture_graphs: OrderedDict[str, dict] = OrderedDict()
_cache_lock = asyncio.Lock()


class ThreadDeletedError(ValueError):
    """P2.2: a turn targeted a thread that has been deleted.

    Subclasses ValueError (backward compatible) but lets routes map it to an
    honest 409 instead of a generic 500."""
    def __init__(self, thread_id: str):
        super().__init__(f"Thread {thread_id} was deleted.")
        self.thread_id = thread_id


def sanitize_lecture_id(lecture_id: str) -> str:
    """Ensure lecture_id is a safe alphanumeric/UUID string to prevent directory traversal."""
    clean_id = Path(lecture_id).name
    if not clean_id or not re.match(r"^[a-zA-Z0-9_-]+$", clean_id):
        raise ValueError(f"Invalid lecture_id: {lecture_id}")
    return clean_id


def configure_sqlite(conn: sqlite3.Connection):
    """Sync PRAGMA tuning used by the short-lived sqlite3 helpers in main.py."""
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
    except Exception:
        pass


async def _open_checkpointer(db_path: Path) -> AsyncSqliteSaver:
    """Open a long-lived aiosqlite connection + AsyncSqliteSaver for a lecture."""
    conn = await aiosqlite.connect(str(db_path))
    await conn.execute("PRAGMA journal_mode=WAL;")
    await conn.execute("PRAGMA busy_timeout=5000;")
    checkpointer = AsyncSqliteSaver(conn)
    await checkpointer.setup()
    return checkpointer


async def _build_graph_for_lecture(clean_id: str):
    lecture_dir = Path("outputs") / clean_id
    db_path = lecture_dir / "tutor" / "checkpoints.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    checkpointer = await _open_checkpointer(db_path)
    graph = build_graph(checkpointer, output_dir=str(lecture_dir))
    return graph, checkpointer, db_path


async def _aget_or_create_lecture_graph(lecture_id: str):
    """
    Return (graph, lock) for the given lecture, building and caching it on
    first use. LRU-bounded: when the cache exceeds TUTOR_MAX_CACHED_GRAPHS the
    least-recently-used lecture's connection is closed and its graph dropped.

    P2.3: the slow build runs OUTSIDE `_cache_lock` (double-checked insert) so
    one lecture's slow connect/checkpointer.setup never serializes lookups for
    every other lecture.
    """
    clean_id = sanitize_lecture_id(lecture_id)

    async with _cache_lock:
        entry = _lecture_graphs.get(clean_id)
        if entry is not None:
            _lecture_graphs.move_to_end(clean_id)
            return entry["graph"], entry["lock"]

    # Slow path (no lock held): open the checkpointer + build the graph.
    graph, checkpointer, db_path = await _build_graph_for_lecture(clean_id)
    new_entry = {
        "graph": graph,
        "lock": asyncio.Lock(),
        "conn": checkpointer.conn,
        "db_path": db_path,
    }

    evicted: list[tuple[str, dict]] = []
    async with _cache_lock:
        entry = _lecture_graphs.get(clean_id)
        if entry is not None:
            # Another concurrent builder won the race — use theirs.
            _lecture_graphs.move_to_end(clean_id)
        else:
            _lecture_graphs[clean_id] = new_entry
            _lecture_graphs.move_to_end(clean_id)
            entry = new_entry
            while len(_lecture_graphs) > TUTOR_MAX_CACHED_GRAPHS:
                _old_id, old_entry = _lecture_graphs.popitem(last=False)
                evicted.append((_old_id, old_entry))

    if entry is not new_entry and entry["graph"] is not graph:
        # We lost the build race — close OUR freshly-opened connection.
        try:
            await checkpointer.conn.close()
        except Exception:  # noqa: BLE001
            pass

    # Close evicted connections and drop their context caches outside the
    # cache lock so a slow close/delete never blocks other lookups.
    for _old_id, old_entry in evicted:
        try:
            # P7.x: purge the lecture's Gemini context caches so they don't
            # linger (TTL is 30 min but the graph is gone — drop now).
            from tutor import cache as tutor_cache

            tutor_cache.delete_lecture_caches(_old_id)
        except Exception:  # noqa: BLE001
            pass
        try:
            await old_entry["conn"].close()
        except Exception:
            pass

    return entry["graph"], entry["lock"]


async def _aget_default_graph():
    """Lazily build + cache the global default graph."""
    global _default_graph
    if _default_graph is not None:
        return _default_graph
    async with _default_graph_init_lock:
        if _default_graph is not None:
            return _default_graph
        CHECKPOINT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        checkpointer = await _open_checkpointer(CHECKPOINT_DB_PATH)
        _default_graph = build_graph(checkpointer)
    return _default_graph


def get_lecture_db_path(lecture_id: str) -> Path:
    """Return the path to the SQLite checkpoints DB for a lecture."""
    clean_id = sanitize_lecture_id(lecture_id)
    return Path("outputs") / clean_id / "tutor" / "checkpoints.sqlite"


# ---------------------------------------------------------------------------
# Public API — invoke the tutor for a specific lecture (async, P4.4)
# ---------------------------------------------------------------------------

def _content_text(content) -> str:
    """Extract plain text from a message's .content (str or Gemini content-block list)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            b.get("text", "") if isinstance(b, dict) else str(b)
            for b in content
        ]
        return "".join(parts)
    return str(content) if content else ""


def _chunk_text(chunk) -> str:
    """Extract the incremental text from an on_chat_model_stream chunk.

    The chunk is an AIMessageChunk whose .content may be a plain string OR a
    list of content blocks (Gemini 'thinking' models return {"text": ...}
    blocks). Empty chunks (chunk_position="last") yield "".
    """
    content = getattr(chunk, "content", "")
    if isinstance(content, list):
        parts = [
            b.get("text", "")
            for b in content
            if isinstance(b, dict) and b.get("text")
        ]
        return "".join(parts)
    return content if isinstance(content, str) else (str(content) if content else "")


def _cached_turn(snapshot, user_question: str, thread_id: str) -> dict | None:
    """If the current question was already answered, return the cached turn dict.

    Scans the last 3 HumanMessages (skipping summary/system messages) and finds
    the AI message that IMMEDIATELY follows each one (identity scan, not
    messages.index(), which ==-collides on equal content). Mirrors the dedup
    check used by ainvoke_tutor so /chat and /chat/stream never diverge.
    """
    from langchain_core.messages import HumanMessage, AIMessage

    if not (snapshot and snapshot.values):
        return None
    messages = snapshot.values.get("messages", [])
    dedupe_window = [m for m in reversed(messages) if isinstance(m, HumanMessage)][:3]
    for last_human in dedupe_window:
        if _content_text(last_human.content).strip() == user_question.strip():
            last_ai = None
            seen = False
            for idx, m in enumerate(messages):
                if m is last_human:
                    seen = True
                    continue
                if seen and isinstance(m, AIMessage):
                    last_ai = m
                    break
            if last_ai:
                return {
                    "answer":              _content_text(last_ai.content),
                    "assistant_message_id": last_ai.id,
                    "retrieved_chunks":  snapshot.values.get("retrieved_chunks", []),
                    "retrieved_images":  snapshot.values.get("retrieved_images", []),
                    "verified_citations": snapshot.values.get("verified_citations", []),
                    "chapter_id":        snapshot.values.get("chapter_id"),
                    "thread_id":         thread_id,
                }
    return None


def _thread_exists(db_path: Path, thread_id: str) -> bool:
    """True when the thread should be allowed to continue (not deleted). Runs in a worker
    thread (blocking sqlite3 read) so it never blocks the event loop."""
    try:
        conn = sqlite3.connect(str(db_path), timeout=5.0)
        try:
            if conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='deleted_threads'").fetchone():
                del_cols = [c[1] for c in conn.execute("PRAGMA table_info(deleted_threads)").fetchall()]
                if ":" in thread_id and "user_id" in del_cols:
                    u_scope, bare_tid = thread_id.split(":", 1)
                    if conn.execute("SELECT 1 FROM deleted_threads WHERE thread_id = ? AND user_id = ?", (bare_tid, u_scope)).fetchone():
                        return False
                if conn.execute("SELECT 1 FROM deleted_threads WHERE thread_id = ?", (thread_id,)).fetchone():
                    return False
        finally:
            conn.close()
        return True
    except sqlite3.OperationalError:
        return True  # If DB is locked, we'll let LangGraph handle it


def _register_thread_if_needed(db_path: Path, thread_id: str) -> None:
    """Ensure active thread is recorded in user_threads and un-marked from deleted_threads."""
    try:
        conn = sqlite3.connect(str(db_path), timeout=5.0)
        try:
            conn.execute("CREATE TABLE IF NOT EXISTS user_threads (thread_id TEXT, user_id TEXT DEFAULT '', PRIMARY KEY (thread_id, user_id))")
            ut_cols = [c[1] for c in conn.execute("PRAGMA table_info(user_threads)").fetchall()]
            if "user_id" not in ut_cols:
                try:
                    conn.execute("ALTER TABLE user_threads ADD COLUMN user_id TEXT DEFAULT ''")
                except Exception:
                    pass

            u_scope = ""
            bare_tid = thread_id
            if ":" in thread_id:
                u_scope, bare_tid = thread_id.split(":", 1)

            conn.execute("INSERT OR IGNORE INTO user_threads (thread_id, user_id) VALUES (?, ?)", (bare_tid, u_scope))
            if conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='deleted_threads'").fetchone():
                del_cols = [c[1] for c in conn.execute("PRAGMA table_info(deleted_threads)").fetchall()]
                if "user_id" in del_cols and u_scope:
                    conn.execute("DELETE FROM deleted_threads WHERE thread_id = ? AND user_id = ?", (bare_tid, u_scope))
                else:
                    conn.execute("DELETE FROM deleted_threads WHERE thread_id = ?", (thread_id,))
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass


async def ainvoke_tutor(
    thread_id: str,
    user_question: str,
    lecture_title: str = "",
    lecture_id: str | None = None,
    message_id: str | None = None,
    study_mode: str = "default",
    persona_instructions: str = "",
) -> dict:
    """
    Invoke the tutor graph for a single turn (async).

    If `lecture_id` is provided, the lecture-specific graph and checkpointer
    are used. Otherwise, the global default graph is used (backward
    compatible). Turns on the same lecture serialize via a per-lecture
    asyncio.Lock; turns on different lectures run concurrently.
    """
    # The frontend uses 'default' as the fallback lecture_id when none is
    # active. Treat it like "no lecture" so it uses the global default graph
    # instead of creating a phantom outputs/default/ lecture with no chroma.
    lecture_id = lecture_id if lecture_id and lecture_id != "default" else None

    if lecture_id:
        graph, lock = await _aget_or_create_lecture_graph(lecture_id)
    else:
        graph = await _aget_default_graph()
        lock = _default_turn_lock

    async with lock:
        config = {"configurable": {"thread_id": thread_id}}

        # Determine whether this is the first message in the thread.
        is_new = True
        try:
            snapshot = await graph.aget_state(config)
            is_new = not snapshot or not snapshot.values
        except Exception:
            snapshot = None
            is_new = True

        input_state: dict = {
            "thread_id": thread_id,
            "user_question": user_question,
            "message_id": message_id,
            "study_mode": study_mode,
            "persona_instructions": persona_instructions,
        }
        if is_new and lecture_title:
            input_state["lecture_title"] = lecture_title

        # Deduplication check: if the last few human messages contain one
        # identical to the current question, and an AI response follows it,
        # skip the graph and return the cached answer. Scanning the tail (not
        # just the final message) catches Ask-Nora double-fires and re-asks
        # that land after a summary/system message.
        cached = _cached_turn(snapshot, user_question, thread_id)
        if cached:
            return cached

        # P3: Prevent Zombie Thread Resurrections — verify the thread hasn't
        # been deleted while we were waiting in the queue.
        db_path = get_lecture_db_path(lecture_id) if lecture_id else CHECKPOINT_DB_PATH
        if not await asyncio.to_thread(_thread_exists, db_path, thread_id):
            raise ThreadDeletedError(thread_id)
        await asyncio.to_thread(_register_thread_if_needed, db_path, thread_id)

        result = await graph.ainvoke(input_state, config)

        messages = result.get("messages", [])
        assistant_message_id = None
        if messages:
            from langchain_core.messages import AIMessage
            last_ai = next((m for m in reversed(messages) if isinstance(m, AIMessage)), None)
            if last_ai:
                assistant_message_id = last_ai.id

        return {
            "answer":            result.get("answer", ""),
            "assistant_message_id": assistant_message_id,
            "retrieved_chunks":  result.get("retrieved_chunks", []),
            "retrieved_images":  result.get("retrieved_images", []),
            "verified_citations": result.get("verified_citations", []),
            "chapter_id":        result.get("chapter_id"),
            "thread_id":         thread_id,
        }


async def astream_tutor_tokens(
    thread_id: str,
    user_question: str,
    lecture_title: str = "",
    lecture_id: str | None = None,
    message_id: str | None = None,
    study_mode: str = "default",
    persona_instructions: str = "",
):
    """
    REAL token streaming for a single tutor turn (P6.1).

    Async generator yielding frames on the /chat/stream SSE wire contract:
        {"t": "<token>"}      — incremental text from generate_answer_node
        {"final": {...}}      — same final payload ainvoke_tutor returns

    The graph is streamed with `astream_events(version="v2")`; only
    `on_chat_model_stream` events from the `generate_answer_node` LLM are
    surfaced, so the summarization / query-rewrite / quiz-evaluate LLM calls
    never leak into the visible stream. Runs under the same per-lecture lock
    (and zombie/dedupe guards) as `ainvoke_tutor`, so /chat and /chat/stream
    can never interleave turns on the same thread.
    """
    # Treat 'default' like "no lecture" — same as ainvoke_tutor.
    lecture_id = lecture_id if lecture_id and lecture_id != "default" else None

    if lecture_id:
        graph, lock = await _aget_or_create_lecture_graph(lecture_id)
    else:
        graph = await _aget_default_graph()
        lock = _default_turn_lock

    async with lock:
        config = {"configurable": {"thread_id": thread_id}}

        # First message in the thread?
        is_new = True
        try:
            snapshot = await graph.aget_state(config)
            is_new = not snapshot or not snapshot.values
        except Exception:
            snapshot = None
            is_new = True

        input_state: dict = {
            "thread_id": thread_id,
            "user_question": user_question,
            "message_id": message_id,
            "study_mode": study_mode,
            "persona_instructions": persona_instructions,
        }
        if is_new and lecture_title:
            input_state["lecture_title"] = lecture_title

        # Dedupe: if already answered, stream the cached answer once then stop.
        cached = _cached_turn(snapshot, user_question, thread_id)
        if cached:
            yield {"t": cached["answer"]}
            yield {"final": cached}
            return

        # Prevent zombie-thread resurrections (same guard as ainvoke_tutor).
        db_path = get_lecture_db_path(lecture_id) if lecture_id else CHECKPOINT_DB_PATH
        if not await asyncio.to_thread(_thread_exists, db_path, thread_id):
            raise ThreadDeletedError(thread_id)
        await asyncio.to_thread(_register_thread_if_needed, db_path, thread_id)

        streamed_any = False
        async for event in graph.astream_events(input_state, config, version="v2"):
            if event.get("event") != "on_chat_model_stream":
                continue
            # Only surface tokens the answer generator produced — the
            # summarizer / query rewriter / quiz evaluator LLM calls are
            # internal and must not appear in the visible answer stream.
            # NOTE: the graph node is registered as "generate_answer" (not
            # "generate_answer_node") — match the node name exactly or every
            # streamed event is dropped and the whole answer is re-emitted via
            # the no-stream fallback (P6.1 live-TTFT regression).
            if event.get("metadata", {}).get("langgraph_node") != "generate_answer":
                continue
            text = _chunk_text(event.get("data", {}).get("chunk"))
            if text:
                streamed_any = True
                yield {"t": text}

        # Read the committed final state to build the payload (the graph
        # checkpointer has already written the completed turn).
        final_state: dict = {}
        try:
            final_snap = await graph.aget_state(config)
            if final_snap and final_snap.values:
                final_state = final_snap.values
        except Exception:
            final_state = {}

        answer = _content_text(final_state.get("answer", ""))

        # Quiz / command paths answer without an LLM stream — emit the whole
        # answer as a single frame so the frontend still has text to render.
        if not streamed_any and answer:
            yield {"t": answer}

        messages = final_state.get("messages", [])
        assistant_message_id = None
        if messages:
            from langchain_core.messages import AIMessage
            last_ai = next((m for m in reversed(messages) if isinstance(m, AIMessage)), None)
            if last_ai:
                assistant_message_id = last_ai.id

        yield {"final": {
            "assistant_message_id": assistant_message_id,
            "retrieved_chunks":  final_state.get("retrieved_chunks", []),
            "retrieved_images":  final_state.get("retrieved_images", []),
            "verified_citations": final_state.get("verified_citations", []),
            "chapter_id":        final_state.get("chapter_id"),
            "thread_id":         thread_id,
        }}
