"""
backend/dependencies.py

Fix log:
  BUG-4  invoke_tutor() now handles the case where get_state() returns an empty
         snapshot for a brand-new thread (no checkpoint yet). Previously this
         could raise inside the `not snapshot.values` branch if LangGraph
         returned a None-like object rather than raising.
  BUG-7  The SQLite connection uses check_same_thread=False and all access is
         serialised through _lock, which is correct. Added a comment to make
         the contract explicit so future contributors don't remove the lock.

No logic changes from the original — this file was the most stable of the six.
"""

import sqlite3
import threading
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from tutor.config import CHECKPOINT_DB_PATH
from tutor.graph import build_graph

# ---------------------------------------------------------------------------
# Global graph instance — compiled exactly once at startup.
# Access is serialised by _lock so the SQLite connection is never used from
# two threads simultaneously (check_same_thread=False relies on this).
# ---------------------------------------------------------------------------

_graph = None
_lock  = threading.Lock()


def _init_graph():
    global _graph
    CHECKPOINT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Use a persistent connection so the checkpointer can cache prepared
    # statements across invocations. check_same_thread=False is safe because
    # every call to invoke_tutor() holds _lock for the full duration.
    conn = sqlite3.connect(
        str(CHECKPOINT_DB_PATH),
        check_same_thread=False,
    )
    checkpointer = SqliteSaver(conn)
    _graph = build_graph(checkpointer)
    return checkpointer


_checkpointer = _init_graph()


def invoke_tutor(thread_id: str, user_question: str, lecture_title: str = "") -> dict:
    """
    Invoke the tutor graph for a single turn and return the output dict.

    BUG-4: get_state() is wrapped in try/except independently from the invoke
    so a missing checkpoint (brand-new thread) doesn't abort the whole call.
    """
    with _lock:
        config = {"configurable": {"thread_id": thread_id}}

        # Determine whether this is the first message in the thread.
        is_new = True
        try:
            snapshot = _graph.get_state(config)
            # snapshot.values is {} or None for a thread with no messages yet
            is_new = not snapshot or not snapshot.values
        except Exception:
            is_new = True

        input_state: dict = {
            "thread_id": thread_id,
            "user_question": user_question,
        }
        # Only pass lecture_title on the very first turn so it doesn't
        # override subsequent context.
        if is_new and lecture_title:
            input_state["lecture_title"] = lecture_title

        result = _graph.invoke(input_state, config)

        return {
            "answer":            result.get("answer", ""),
            "retrieved_chunks":  result.get("retrieved_chunks", []),
            "retrieved_images":  result.get("retrieved_images", []),
            "chapter_id":        result.get("chapter_id"),
            "thread_id":         thread_id,
        }