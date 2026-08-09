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
    return AsyncSqliteSaver(conn)


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
    """
    clean_id = sanitize_lecture_id(lecture_id)
    async with _cache_lock:
        entry = _lecture_graphs.get(clean_id)
        if entry is not None:
            _lecture_graphs.move_to_end(clean_id)
            return entry["graph"], entry["lock"]

        graph, checkpointer, db_path = await _build_graph_for_lecture(clean_id)
        entry = {
            "graph": graph,
            "lock": asyncio.Lock(),
            "conn": checkpointer.conn,
            "db_path": db_path,
        }
        _lecture_graphs[clean_id] = entry
        _lecture_graphs.move_to_end(clean_id)

        evicted: list[dict] = []
        while len(_lecture_graphs) > TUTOR_MAX_CACHED_GRAPHS:
            _old_id, old_entry = _lecture_graphs.popitem(last=False)
            evicted.append(old_entry)

    # Close evicted connections outside the cache lock so a slow close never
    # blocks other lookups.
    for old_entry in evicted:
        try:
            await old_entry["conn"].close()
        except Exception:
            pass

    return graph, entry["lock"]


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

def _thread_exists(db_path: Path, thread_id: str) -> bool:
    """True when the thread should be allowed to continue. Runs in a worker
    thread (blocking sqlite3 read) so it never blocks the event loop."""
    try:
        conn = sqlite3.connect(str(db_path), timeout=5.0)
        try:
            if conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_threads'").fetchone():
                if not conn.execute("SELECT 1 FROM user_threads WHERE thread_id = ?", (thread_id,)).fetchone():
                    return False
        finally:
            conn.close()
        return True
    except sqlite3.OperationalError:
        return True  # If DB is locked, we'll let LangGraph handle it


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
        from langchain_core.messages import HumanMessage, AIMessage
        if not is_new and snapshot and snapshot.values:
            messages = snapshot.values.get("messages", [])
            dedupe_window = [m for m in reversed(messages) if isinstance(m, HumanMessage)][:3]
            for last_human in dedupe_window:
                if last_human.content.strip() == user_question.strip():
                    last_ai = None
                    # Scan from the actual position of this human message
                    # (messages.index() uses == so it can hit an earlier equal
                    # message; track position explicitly via enumerate).
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
                            "answer":            last_ai.content,
                            "assistant_message_id": last_ai.id,
                            "retrieved_chunks":  snapshot.values.get("retrieved_chunks", []),
                            "retrieved_images":  snapshot.values.get("retrieved_images", []),
                            "verified_citations": snapshot.values.get("verified_citations", []),
                            "chapter_id":        snapshot.values.get("chapter_id"),
                            "thread_id":         thread_id,
                        }

        # P3: Prevent Zombie Thread Resurrections — verify the thread hasn't
        # been deleted while we were waiting in the queue.
        db_path = get_lecture_db_path(lecture_id) if lecture_id else CHECKPOINT_DB_PATH
        if not await asyncio.to_thread(_thread_exists, db_path, thread_id):
            raise ValueError(f"Thread {thread_id} was deleted.")

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
