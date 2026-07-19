"""
backend/dependencies.py

Provides the NorAI tutor graph, one instance per lecture.
Each lecture owns its own SQLite checkpointer (stored under
outputs/{lecture_id}/tutor/) and a dedicated lock, so conversations
from different lectures are completely isolated.
"""

import sqlite3
import threading
from pathlib import Path
from typing import Dict

from langgraph.checkpoint.sqlite import SqliteSaver
from tutor.config import CHECKPOINT_DB_PATH   # fallback for the default lecture
from tutor.graph import build_graph


# ---------------------------------------------------------------------------
# Per‑lecture graph cache
# ---------------------------------------------------------------------------

# Global default graph (used when no lecture_id is supplied)
_default_graph = None
_default_lock = threading.Lock()

# Cache: lecture_id -> { "graph": ..., "lock": ... }
_lecture_graphs: Dict[str, dict] = {}
_cache_lock = threading.Lock()


def _init_graph_for_lecture(lecture_id: str):
    lecture_dir = Path("outputs") / lecture_id
    db_path = lecture_dir / "tutor" / "checkpoints.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    graph = build_graph(checkpointer, output_dir=str(lecture_dir))
    return graph


def _init_default_graph():
    """Build the global default graph (keeps backward compatibility)."""
    global _default_graph
    CHECKPOINT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(CHECKPOINT_DB_PATH), check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    _default_graph = build_graph(checkpointer)


# Initialise the default graph once at startup
_init_default_graph()


def _get_or_create_lecture_graph(lecture_id: str):
    """
    Return (graph, lock) for the given lecture.
    Caches each graph so it's built only once per lecture.
    """
    with _cache_lock:
        if lecture_id not in _lecture_graphs:
            graph = _init_graph_for_lecture(lecture_id)
            lock = threading.Lock()
            _lecture_graphs[lecture_id] = {"graph": graph, "lock": lock}
        entry = _lecture_graphs[lecture_id]
        return entry["graph"], entry["lock"]

def get_lecture_db_path(lecture_id: str) -> Path:
    """Return the path to the SQLite checkpoints DB for a lecture."""
    return Path("outputs") / lecture_id / "tutor" / "checkpoints.sqlite"
# ---------------------------------------------------------------------------
# Public API — invoke the tutor for a specific lecture
# ---------------------------------------------------------------------------

def invoke_tutor(
    thread_id: str,
    user_question: str,
    lecture_title: str = "",
    lecture_id: str | None = None,
    message_id: str | None = None,
) -> dict:
    """
    Invoke the tutor graph for a single turn.

    If `lecture_id` is provided, the lecture‑specific graph and checkpointer
    are used. Otherwise, the global default graph is used (backward compatible).
    """
    if lecture_id:
        graph, lock = _get_or_create_lecture_graph(lecture_id)
    else:
        graph = _default_graph
        lock = _default_lock

    with lock:
        config = {"configurable": {"thread_id": thread_id}}

        # Determine whether this is the first message in the thread.
        is_new = True
        try:
            snapshot = graph.get_state(config)
            is_new = not snapshot or not snapshot.values
        except Exception:
            is_new = True

        input_state: dict = {
            "thread_id": thread_id,
            "user_question": user_question,
            "message_id": message_id,
        }
        if is_new and lecture_title:
            input_state["lecture_title"] = lecture_title

        # Deduplication check: if the last human message is identical to the current 
        # question, and an AI response follows it, skip the graph and return the cached answer.
        from langchain_core.messages import HumanMessage, AIMessage
        if not is_new and snapshot and snapshot.values:
            messages = snapshot.values.get("messages", [])
            # Find the last human message
            last_human = next((m for m in reversed(messages) if isinstance(m, HumanMessage)), None)
            if last_human and last_human.content.strip() == user_question.strip():
                # Check if there is an AI response after it
                last_ai = next((m for m in reversed(messages) if isinstance(m, AIMessage)), None)
                if last_ai and messages.index(last_ai) > messages.index(last_human):
                    return {
                        "answer":            last_ai.content,
                        "assistant_message_id": last_ai.id,
                        "retrieved_chunks":  snapshot.values.get("retrieved_chunks", []),
                        "retrieved_images":  snapshot.values.get("retrieved_images", []),
                        "chapter_id":        snapshot.values.get("chapter_id"),
                        "thread_id":         thread_id,
                    }

        # Phase 3: Prevent Zombie Thread Resurrections
        # Verify the thread hasn't been deleted while we were waiting in the queue.
        db_path = get_lecture_db_path(lecture_id) if lecture_id else CHECKPOINT_DB_PATH
        try:
            conn = sqlite3.connect(str(db_path), timeout=5.0)
            if conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_threads'").fetchone():
                if not conn.execute("SELECT 1 FROM user_threads WHERE thread_id = ?", (thread_id,)).fetchone():
                    conn.close()
                    raise ValueError(f"Thread {thread_id} was deleted.")
            conn.close()
        except sqlite3.OperationalError:
            pass  # If DB is locked, we'll let LangGraph handle it

        result = graph.invoke(input_state, config)

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
            "chapter_id":        result.get("chapter_id"),
            "thread_id":         thread_id,
        }