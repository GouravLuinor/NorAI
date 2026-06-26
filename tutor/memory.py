"""
memory.py

Wraps SqliteSaver setup. SqliteSaver.from_conn_string is itself a
context manager (`with SqliteSaver.from_conn_string(path) as cp: ...`)
— get_checkpointer() here is a thin wrapper so callers (graph.py,
cli.py) don't need to know the connection-string path or import
langgraph.checkpoint.sqlite directly.

SECURITY NOTE: langgraph-checkpoint-sqlite's own README flags that
checkpoint deserialization should be restricted to known-safe types
via LANGGRAPH_STRICT_MSGPACK=true (or an explicit allowed_msgpack_modules
list), to prevent arbitrary code execution if the checkpoint DB file
is ever compromised/tampered with. Set here, once, before any
SqliteSaver is constructed — not something to skip just because this
is "only" a local SQLite file for now; Postgres migration later
doesn't remove the need for this.

KNOWN LIMITATION — NOT YET ADDRESSED, DO NOT FORGET:
SqliteSaver is synchronous and does not handle concurrent writes
across multiple threads/async tasks safely — this is stated directly
in its own docstring ("meant for lightweight, synchronous use cases...
does not scale to multiple threads"). It is fine for THIS package's
current use (a single-process CLI test harness, one graph.invoke()
call at a time, fully sequential) — there is no concurrent access
happening here. It will NOT be fine the moment this becomes a real
backend serving multiple students/sessions concurrently (e.g. a web
server handling several requests at once), even though each student
has their own thread_id — the danger isn't thread_id collisions
(those are already isolated, see graph.py's tests), it's multiple OS
threads/async tasks hitting the same underlying sqlite3.Connection at
once, which sqlite3 connections aren't safe for without serialization
SqliteSaver doesn't provide.

THE FIX, WHEN THAT TIME COMES: swap to
langgraph.checkpoint.sqlite.aio.AsyncSqliteSaver. This is NOT a
drop-in swap — it requires:
  - `async with AsyncSqliteSaver.from_conn_string(...) as cp:` instead
    of `with SqliteSaver.from_conn_string(...) as cp:`
  - graph.ainvoke()/.astream() instead of .invoke()/.stream() everywhere
  - generate_answer_node (and any future node making an LLM call)
    becoming `async def` and using `llm.ainvoke(...)` instead of
    `llm.invoke(...)` — calling the sync .invoke() inside an async
    node would block the event loop during the Gemini call, defeating
    the entire point of going async
  - cli.py's run_cli() becoming an async function, run via asyncio.run()

Deliberately NOT done yet (confirmed with the user) because there is
no real concurrency to fix yet — this is the single thing to revisit
first when this package grows beyond a solo-dev CLI into anything
serving more than one request at a time.
"""

import os

os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")

from contextlib import contextmanager
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

from tutor.config import CHECKPOINT_DB_PATH


@contextmanager
def get_checkpointer(db_path: str | Path = CHECKPOINT_DB_PATH):
    """
    Yields a SqliteSaver checkpointer backed by db_path, creating the
    parent directory if needed. Use as:

        with get_checkpointer() as checkpointer:
            graph = build_graph(checkpointer)
            ...

    The checkpointer (and its underlying SQLite connection) must stay
    open for as long as the graph is being invoked — closing it after
    building the graph but before calling .invoke()/.stream() will
    break memory persistence. This is why graph construction and graph
    usage need to happen inside the same `with` block (see cli.py).
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with SqliteSaver.from_conn_string(str(db_path)) as checkpointer:
        yield checkpointer