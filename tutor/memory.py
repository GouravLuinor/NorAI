"""
memory.py

Wraps SqliteSaver / AsyncSqliteSaver setup.

- `get_checkpointer()`  — synchronous SqliteSaver (kept for the CLI/tests).
- `get_async_checkpointer()` — AsyncSqliteSaver for the backend, where a
  turn must never block the event loop and concurrent turns on different
  lectures share the process safely (P4.4).

SECURITY NOTE: langgraph-checkpoint-sqlite's own README flags that
checkpoint deserialization should be restricted to known-safe types
via LANGGRAPH_STRICT_MSGPACK=true (or an explicit allowed_msgpack_modules
list), to prevent arbitrary code execution if the checkpoint DB file
is ever compromised/tampered with. Set here, once, before any
SqliteSaver is constructed — not something to skip just because this
is "only" a local SQLite file for now; Postgres migration later
doesn't remove the need for this.
"""

import os

os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")

from contextlib import asynccontextmanager, contextmanager
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from tutor.config import CHECKPOINT_DB_PATH


@contextmanager
def get_checkpointer(db_path: str | Path = CHECKPOINT_DB_PATH):
    """
    Yields a synchronous SqliteSaver checkpointer backed by db_path,
    creating the parent directory if needed. Use as:

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


@asynccontextmanager
async def get_async_checkpointer(db_path: str | Path = CHECKPOINT_DB_PATH):
    """
    Yields an AsyncSqliteSaver checkpointer backed by db_path (P4.4).

    AsyncSqliteSaver uses a single aiosqlite connection and serialises
    writes internally, so it is safe for concurrent access from multiple
    async tasks (unlike the sync SqliteSaver). As with the sync variant,
    the checkpointer must stay open for the graph's lifetime — the
    backend holds it in the per-lecture graph cache and closes it when
    the entry is evicted.

    Use as:

        async with get_async_checkpointer(db_path) as checkpointer:
            graph = build_graph(checkpointer)
            result = await graph.ainvoke(state, config)
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    async with AsyncSqliteSaver.from_conn_string(str(db_path)) as checkpointer:
        yield checkpointer