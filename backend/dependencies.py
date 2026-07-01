"""
backend/dependencies.py

Creates the NorAI tutor graph at startup and provides a thread-safe
invocation wrapper.
"""

import sqlite3
import threading
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from tutor.config import CHECKPOINT_DB_PATH
from tutor.graph import build_graph

# -- Global graph instance (compiled once) --
_graph = None
_lock = threading.Lock()

def _init_graph():
    global _graph
    CHECKPOINT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Create a persistent connection ourselves and hand it to SqliteSaver.
    # This bypasses the context-manager issue of from_conn_string().
    conn = sqlite3.connect(
        str(CHECKPOINT_DB_PATH),
        check_same_thread=False,   # we serialize access with a lock
    )
    
    checkpointer = SqliteSaver(conn)
    _graph = build_graph(checkpointer)
    return checkpointer

_checkpointer = _init_graph()

def invoke_tutor(thread_id: str, user_question: str, lecture_title: str = "") -> dict:
    """Invoke the tutor graph for a single turn and return the results."""
    with _lock:
        config = {"configurable": {"thread_id": thread_id}}

        try:
            snapshot = _graph.get_state(config)
            is_new = not snapshot.values
        except Exception:
            is_new = True

        input_state = {
            "thread_id": thread_id,
            "user_question": user_question,
        }
        if is_new and lecture_title:
            input_state["lecture_title"] = lecture_title

        result = _graph.invoke(input_state, config)

        return {
            "answer": result.get("answer", ""),
            "retrieved_chunks": result.get("retrieved_chunks", []),
            "retrieved_images": result.get("retrieved_images", []),
            "chapter_id": result.get("chapter_id"),
            "thread_id": thread_id,
        }