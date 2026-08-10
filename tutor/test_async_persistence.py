"""
test_async_persistence.py — P4.4 offline tests for the async tutor path.

Covers, WITHOUT any real Gemini calls (the LLM is stubbed out):
  1. Cross-turn persistence: AsyncSqliteSaver checkpoints survive across
     `ainvoke` calls and threads stay memory-isolated.
  2. LRU cache eviction in backend.dependencies: adding more lectures than
     TUTOR_MAX_CACHED_GRAPHS evicts the least-recently-used one and closes
     its sqlite connection.
  3. Concurrency semantics: turns on the SAME lecture serialize (the
     per-lecture asyncio.Lock), turns on DIFFERENT lectures run concurrently.

Run:
    python -m pytest tutor/test_async_persistence.py -v
    # or without pytest:
    python tutor/test_async_persistence.py
"""

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))

import tutor.llm as tllm  # noqa: E402

from tutor.graph import build_graph  # noqa: E402
from tutor.memory import get_async_checkpointer  # noqa: E402
import tempfile  # noqa: E402


# ── Stubbed LLM ──────────────────────────────────────────────────────────────

# Shared bookkeeping so the test can observe concurrency.
_LLM_ACTIVE = 0
_LLM_MAX_ACTIVE = 0
_LLM_DELAY = 0.0
_LLM_CALLS = 0


def _reset_llm_stats(delay: float = 0.0):
    global _LLM_ACTIVE, _LLM_MAX_ACTIVE, _LLM_CALLS, _LLM_DELAY
    _LLM_ACTIVE = 0
    _LLM_MAX_ACTIVE = 0
    _LLM_CALLS = 0
    _LLM_DELAY = delay


class FakeLLM:
    """Replaces ChatGoogleGenerativeAI. `ainvoke` only (P4.4 nodes are async)."""

    def __init__(self, **kwargs):
        pass

    async def ainvoke(self, messages):
        global _LLM_ACTIVE, _LLM_MAX_ACTIVE, _LLM_CALLS
        _LLM_ACTIVE += 1
        _LLM_MAX_ACTIVE = max(_LLM_MAX_ACTIVE, _LLM_ACTIVE)
        _LLM_CALLS += 1
        try:
            if _LLM_DELAY:
                await asyncio.sleep(_LLM_DELAY)
            return SimpleNamespace(content="stub tutor answer")
        finally:
            _LLM_ACTIVE -= 1


def _patch_llm():
    original = tllm.make_chat_llm
    tllm.make_chat_llm = lambda **kwargs: FakeLLM(**kwargs)  # type: ignore[assignment]
    return original


def _restore_llm(original):
    tllm.make_chat_llm = original


_turn_counter = 0


async def _run_turn(graph, thread_id: str, question: str) -> dict:
    global _turn_counter
    _turn_counter += 1
    config = {"configurable": {"thread_id": thread_id}}
    input_state = {
        "thread_id": thread_id,
        "user_question": question,
        "message_id": f"msg-{thread_id}-{_turn_counter}",  # unique per turn
        "study_mode": "default",
        "persona_instructions": "",
        "lecture_title": "Test Lecture",
    }
    return await graph.ainvoke(input_state, config)


async def _close_and_clear_cache(deps):
    """Close every cached aiosqlite connection (on this loop) then clear the
    cache, so no worker threads outlive the event loop."""
    for entry in list(deps._lecture_graphs.values()):
        try:
            await entry["conn"].close()
        except Exception:
            pass
    deps._lecture_graphs.clear()


# ── 1. Cross-turn persistence + thread isolation ─────────────────────────────

def test_async_checkpoint_persistence():
    async def run():
        original = _patch_llm()
        _reset_llm_stats()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                db = str(Path(tmp) / "cp.sqlite")
                async with get_async_checkpointer(db) as cp:
                    graph = build_graph(cp, output_dir=tmp)

                    await _run_turn(graph, "thread-a", "What is a stack?")
                    await _run_turn(graph, "thread-b", "Define a queue.")

                    # Thread A must remember its own first turn…
                    snap_a = await graph.aget_state({"configurable": {"thread_id": "thread-a"}})
                    msgs_a = snap_a.values.get("messages", [])
                    # …and must NOT contain thread B's turn (isolation).
                    all_text = " ".join(str(m.content) for m in msgs_a).lower()
                    assert "what is a stack?" in all_text
                    assert "define a queue" not in all_text

                    # A second turn on thread A accumulates history (persistence).
                    await _run_turn(graph, "thread-a", "What is a stack?")
                    snap_a2 = await graph.aget_state({"configurable": {"thread_id": "thread-a"}})
                    msgs_a2 = snap_a2.values.get("messages", [])
                    assert len(msgs_a2) > len(msgs_a)
        finally:
            _restore_llm(original)

    asyncio.run(run())


# ── 2. LRU eviction of the per-lecture graph cache ───────────────────────────

def test_lru_eviction():
    async def run():
        import backend.dependencies as deps

        original_cap = deps.TUTOR_MAX_CACHED_GRAPHS
        deps.TUTOR_MAX_CACHED_GRAPHS = 2
        created = []
        try:
            # Cache must be empty so eviction math is deterministic.
            await _close_and_clear_cache(deps)

            g_a, _ = await deps._aget_or_create_lecture_graph("lru-a")
            created.append("lru-a")
            g_b, _ = await deps._aget_or_create_lecture_graph("lru-b")
            created.append("lru-b")
            assert "lru-a" in deps._lecture_graphs
            assert "lru-b" in deps._lecture_graphs

            # Touching a makes it MRU; adding c must evict b (LRU).
            await deps._aget_or_create_lecture_graph("lru-a")
            g_c, _ = await deps._aget_or_create_lecture_graph("lru-c")
            created.append("lru-c")

            assert set(deps._lecture_graphs.keys()) == {"lru-a", "lru-c"}
            assert "lru-b" not in deps._lecture_graphs

            # Same key returns the SAME graph + lock (cache hit path).
            g_a2, lock_a2 = await deps._aget_or_create_lecture_graph("lru-a")
            assert g_a2 is g_a
            assert g_a is not g_c
        finally:
            await _close_and_clear_cache(deps)
            deps.TUTOR_MAX_CACHED_GRAPHS = original_cap
            import shutil
            for lid in created:
                shutil.rmtree(Path("outputs") / lid, ignore_errors=True)

    asyncio.run(run())


# ── 3. Concurrency semantics ─────────────────────────────────────────────────

def test_same_lecture_serializes_different_lectures_concurrent():
    async def run():
        import backend.dependencies as deps
        import shutil

        original = _patch_llm()
        await _close_and_clear_cache(deps)
        try:
            # Same lecture returns the SAME lock object (serialization point);
            # different lectures return DIFFERENT locks.
            g_same, lock_same = await deps._aget_or_create_lecture_graph("par-same")
            g_same2, lock_same2 = await deps._aget_or_create_lecture_graph("par-same")
            g_other, lock_other = await deps._aget_or_create_lecture_graph("par-other")
            assert lock_same is lock_same2
            assert lock_same is not lock_other

            async def turn(graph, lock, tid: str):
                # Mirrors ainvoke_tutor: the per-lecture lock is held across
                # the whole graph.ainvoke.
                async with lock:
                    config = {"configurable": {"thread_id": tid}}
                    return await graph.ainvoke(
                        {"thread_id": tid, "user_question": f"q-{tid}",
                         "study_mode": "default", "persona_instructions": ""},
                        config,
                    )

            # Two turns on the SAME lecture → serialized → LLM calls never overlap.
            _reset_llm_stats(delay=0.05)
            await asyncio.gather(turn(g_same, lock_same, "s1"), turn(g_same, lock_same, "s2"))
            assert _LLM_MAX_ACTIVE == 1, f"same-lecture LLM calls overlapped ({_LLM_MAX_ACTIVE})"

            # One turn on each of two lectures → concurrent → LLM calls overlap.
            _reset_llm_stats(delay=0.05)
            await asyncio.gather(turn(g_same, lock_same, "y1"), turn(g_other, lock_other, "y2"))
            assert _LLM_MAX_ACTIVE == 2, f"cross-lecture LLM calls did NOT overlap ({_LLM_MAX_ACTIVE})"
        finally:
            await _close_and_clear_cache(deps)
            _restore_llm(original)
            for lid in ("par-same", "par-other"):
                shutil.rmtree(Path("outputs") / lid, ignore_errors=True)

    asyncio.run(run())


if __name__ == "__main__":
    import traceback

    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except Exception:
                failures += 1
                print(f"FAIL {name}")
                traceback.print_exc()
    sys.exit(1 if failures else 0)
