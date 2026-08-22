"""
test_tutor_streaming.py — P6.1 offline tests for REAL token streaming.

Covers, WITHOUT any real Gemini calls (the LLM is stubbed):
  1. Real streaming: astream_tutor_tokens surfaces the generate_answer_node
     tokens one-by-one; concatenating them reproduces the stub answer; the
     final frame carries the committed turn's metadata.
  2. Node filtering: tokens from rewrite_query_node (and any other internal
     LLM call) never leak into the visible stream.
  3. No-stream fallback: when the answer is produced without an LLM stream
     (quiz / command paths), the whole answer is emitted as a single frame.
  4. Dedup: re-asking the same question returns the cached answer without
     making any further LLM call.
  5. Zombie-thread guard: a deleted thread raises instead of streaming.

Run:
    python tutor/test_tutor_streaming.py
"""

import asyncio
import sys
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))

import tutor.llm as tllm  # noqa: E402
from tutor.graph import build_graph  # noqa: E402


# ── LLM stubs ────────────────────────────────────────────────────────────────

_GEN_ANSWER = "The stack is a LIFO data structure."
_REWRITE_TEXT = "rewritten-query-token"


def _patch_llm(fake):
    original = tllm.make_chat_llm
    tllm.make_chat_llm = lambda **kwargs: fake  # type: ignore[assignment]
    return original


def _restore_llm(original):
    tllm.make_chat_llm = original


class _PlainFakeLLM:
    """Fake with ainvoke + astream but NOT a BaseChatModel — it yields the
    whole answer as one streamed chunk, yet LangChain's tracer never emits
    on_chat_model_stream events for it, so the graph answers while
    astream_tutor_tokens sees no token events (the quiz/command fallback
    path: one whole-answer frame)."""

    calls = 0

    def __init__(self, **kwargs):
        pass

    async def ainvoke(self, messages):
        _PlainFakeLLM.calls += 1
        return SimpleNamespace(content=_GEN_ANSWER)

    async def astream(self, messages):
        _PlainFakeLLM.calls += 1
        yield SimpleNamespace(content=_GEN_ANSWER)


@asynccontextmanager
async def _make_graph(tmp: str):
    """Build a tutor graph over a fresh temp checkpointer (no chroma, no API).

    Context manager so the AsyncSqliteSaver connection stays open for the
    graph's lifetime (mirrors how the backend keeps the checkpointer alive).
    """
    from tutor.memory import get_async_checkpointer

    db = str(Path(tmp) / "cp.sqlite")
    async with get_async_checkpointer(db) as cp:
        graph = build_graph(cp, output_dir=tmp)
        yield graph


async def _patch_graph_into_deps(graph, tmp: str):
    """Route astream_tutor_tokens at the given lecture_id to our temp graph."""
    import backend.dependencies as deps

    orig_get = deps._aget_or_create_lecture_graph
    orig_path = deps.get_lecture_db_path
    lock = asyncio.Lock()

    async def _fake_get(lid):
        return graph, lock

    deps._aget_or_create_lecture_graph = _fake_get  # type: ignore[assignment]
    deps.get_lecture_db_path = lambda lid: Path(tmp) / "cp.sqlite"  # type: ignore[assignment]
    return orig_get, orig_path


def _restore_graph_patch(deps, orig_get, orig_path):
    deps._aget_or_create_lecture_graph = orig_get
    deps.get_lecture_db_path = orig_path


def _frames(tokens_and_finals):
    tokens = [f["t"] for f in tokens_and_finals if "t" in f]
    finals = [f["final"] for f in tokens_and_finals if "final" in f]
    return tokens, finals


async def _stream_turn(deps, thread_id, question, lecture_id="test"):
    out = []
    async for frame in deps.astream_tutor_tokens(
        thread_id=thread_id,
        user_question=question,
        lecture_title="Test Lecture",
        lecture_id=lecture_id,
    ):
        out.append(frame)
    return out


# ── 1. Real token streaming ──────────────────────────────────────────────────

def test_real_token_streaming():
    async def run():
        from langchain_core.language_models.fake_chat_models import GenericFakeChatModel

        with tempfile.TemporaryDirectory() as tmp:
            async with _make_graph(tmp) as graph:
                # P3.1: a first turn skips the rewrite hop entirely, so the
                # queue holds ONLY the answer call.
                fake = GenericFakeChatModel(messages=iter([_GEN_ANSWER]))
                orig_llm = _patch_llm(fake)

                import backend.dependencies as deps
                orig_get, orig_path = await _patch_graph_into_deps(graph, tmp)
                try:
                    frames = await _stream_turn(deps, "th-stream", "What is a stack?")
                finally:
                    _restore_graph_patch(deps, orig_get, orig_path)
                    _restore_llm(orig_llm)

        tokens, finals = _frames(frames)
        assert tokens, "expected real token frames"
        assert "".join(tokens) == _GEN_ANSWER, (
            f"tokens did not reassemble to the answer: {''.join(tokens)!r}"
        )
        assert len(finals) == 1, "expected exactly one final frame"
        f = finals[0]
        assert f["thread_id"] == "th-stream"
        assert f["retrieved_chunks"] == []
        assert f["retrieved_images"] == []
        assert f["verified_citations"] == []
        assert f["assistant_message_id"], "expected an assistant_message_id"

    asyncio.run(run())


# ── 2. Node filtering: internal LLM calls never leak ─────────────────────────

def test_only_generate_answer_tokens_surfaced():
    async def run():
        from langchain_core.language_models.fake_chat_models import GenericFakeChatModel

        with tempfile.TemporaryDirectory() as tmp:
            async with _make_graph(tmp) as graph:
                fake = GenericFakeChatModel(messages=iter([_GEN_ANSWER]))
                orig_llm = _patch_llm(fake)

                import backend.dependencies as deps
                orig_get, orig_path = await _patch_graph_into_deps(graph, tmp)
                try:
                    frames = await _stream_turn(deps, "th-filter", "What is a stack?")
                finally:
                    _restore_graph_patch(deps, orig_get, orig_path)
                    _restore_llm(orig_llm)

        tokens, finals = _frames(frames)
        joined = "".join(tokens)
        assert _REWRITE_TEXT not in joined, (
            f"rewrite_query_node tokens leaked into the stream: {joined!r}"
        )
        assert joined == _GEN_ANSWER

    asyncio.run(run())


def test_rewrite_runs_and_is_filtered_on_followup_turns():
    """P3.1 regression: turn 2 HAS prior history, so the rewrite LLM hop runs
    (consuming the first queued message) — and its tokens still never leak."""

    async def run():
        from langchain_core.language_models.fake_chat_models import GenericFakeChatModel

        with tempfile.TemporaryDirectory() as tmp:
            async with _make_graph(tmp) as graph:
                import backend.dependencies as deps
                orig_get, orig_path = await _patch_graph_into_deps(graph, tmp)

                # Turn 1: rewrite skipped → only the answer call is queued.
                fake1 = GenericFakeChatModel(messages=iter([_GEN_ANSWER]))
                orig_llm = _patch_llm(fake1)
                try:
                    await _stream_turn(deps, "th-followup", "What is a stack?")
                finally:
                    _restore_llm(orig_llm)

                # Turn 2: prior Human+AI messages exist → rewrite fires.
                fake2 = GenericFakeChatModel(messages=iter([_REWRITE_TEXT, _GEN_ANSWER]))
                orig_llm = _patch_llm(fake2)
                try:
                    frames = await _stream_turn(deps, "th-followup", "Why is it LIFO?")
                finally:
                    _restore_graph_patch(deps, orig_get, orig_path)
                    _restore_llm(orig_llm)

        tokens, finals = _frames(frames)
        joined = "".join(tokens)
        assert _REWRITE_TEXT not in joined, (
            f"rewrite tokens leaked on follow-up turn: {joined!r}"
        )
        assert joined == _GEN_ANSWER
        assert len(finals) == 1

    asyncio.run(run())


# ── 3. No-stream fallback (quiz / command answers) ───────────────────────────

def test_fallback_emits_full_answer_without_stream():
    async def run():
        _PlainFakeLLM.calls = 0
        fake = _PlainFakeLLM()
        orig_llm = _patch_llm(fake)

        with tempfile.TemporaryDirectory() as tmp:
            async with _make_graph(tmp) as graph:
                import backend.dependencies as deps
                orig_get, orig_path = await _patch_graph_into_deps(graph, tmp)
                try:
                    frames = await _stream_turn(deps, "th-fallback", "Explain queues.")
                finally:
                    _restore_graph_patch(deps, orig_get, orig_path)
                    _restore_llm(orig_llm)

        tokens, finals = _frames(frames)
        assert tokens, "expected the fallback single-token frame"
        assert len(tokens) == 1, f"fallback should emit ONE token frame, got {len(tokens)}"
        assert tokens[0] == _GEN_ANSWER
        assert len(finals) == 1 and finals[0]["thread_id"] == "th-fallback"

    asyncio.run(run())


# ── 4. Dedup: repeated question returns cached answer, no new LLM call ───────

def test_dedup_returns_cached_stream_without_llm():
    async def run():
        fake = _PlainFakeLLM()
        orig_llm = _patch_llm(fake)

        with tempfile.TemporaryDirectory() as tmp:
            async with _make_graph(tmp) as graph:
                import backend.dependencies as deps
                orig_get, orig_path = await _patch_graph_into_deps(graph, tmp)
                try:
                    first = await _stream_turn(deps, "th-dedup", "What is a stack?")
                    first_calls = _PlainFakeLLM.calls
                    second = await _stream_turn(deps, "th-dedup", "What is a stack?")
                    second_calls = _PlainFakeLLM.calls
                finally:
                    _restore_graph_patch(deps, orig_get, orig_path)
                    _restore_llm(orig_llm)

        assert first_calls > 0, "first turn should hit the LLM"
        assert second_calls == first_calls, (
            f"dedup turn made new LLM calls: {first_calls} -> {second_calls}"
        )

        t1, f1 = _frames(first)
        t2, f2 = _frames(second)
        assert "".join(t1) == _GEN_ANSWER
        # Dedup path streams the cached answer in a single frame.
        assert len(t2) == 1 and t2[0] == _GEN_ANSWER
        assert len(f2) == 1 and f2[0]["thread_id"] == "th-dedup"

    asyncio.run(run())


# ── 5. Zombie-thread guard ───────────────────────────────────────────────────

def test_deleted_thread_raises():
    async def run():
        fake = _PlainFakeLLM()
        orig_llm = _patch_llm(fake)

        with tempfile.TemporaryDirectory() as tmp:
            async with _make_graph(tmp) as graph:
                import backend.dependencies as deps
                orig_get, orig_path = await _patch_graph_into_deps(graph, tmp)
                orig_thread_exists = deps._thread_exists
                deps._thread_exists = lambda db, tid: False  # type: ignore[assignment]
                raised = False
                try:
                    async for _ in deps.astream_tutor_tokens(
                        thread_id="th-zombie",
                        user_question="hi",
                        lecture_id="test",
                    ):
                        pass
                except ValueError:
                    raised = True
                finally:
                    deps._thread_exists = orig_thread_exists
                    _restore_graph_patch(deps, orig_get, orig_path)
                    _restore_llm(orig_llm)

        assert raised, "deleted thread should raise ValueError"

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
