"""
test_memory_nodes.py — Unit tests for tutor/nodes.py memory nodes.

Tests load_memory_node (prompt-window rebuild) and save_memory_node
(incremental summarization trigger) WITHOUT making LLM calls — the
summarisation branch is exercised with the LLM stubbed out via mocking.

Run:
    python -m pytest tutor/test_memory_nodes.py -v
    # or without pytest:
    python tutor/test_memory_nodes.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage  # noqa: E402
from langgraph.graph.message import RemoveMessage  # noqa: E402

from tutor.nodes import (  # noqa: E402
    load_memory_node,
    save_memory_node,
    _SUMMARY_PREFIX,
    _SUMMARY_RETAIN_RECENT,
    _SUMMARY_TRIGGER_MSG_COUNT,
    _recent_window,
)


def _conversation(num_turns: int):
    """Build num_turns Human/AI message pairs with explicit ids (the checkpointer
    assigns ids in production; explicit ids make RemoveMessage testable)."""
    msgs = []
    for i in range(num_turns):
        msgs.append(HumanMessage(content=f"question {i}", id=f"h{i}"))
        msgs.append(AIMessage(content=f"answer {i}", id=f"a{i}"))
    return msgs


def _config():
    return {"configurable": {"thread_id": "test-thread"}}


# ── load_memory_node ──────────────────────────────────────────────────────────

def test_load_empty_state_returns_nothing():
    assert load_memory_node({}, _config()) == {}


def test_load_seeds_window_from_messages():
    state = {"messages": _conversation(4)}  # 8 messages
    out = load_memory_node(state, _config())
    context = out["context_messages"]
    # Window = last _SUMMARY_RETAIN_RECENT messages, no summary yet
    assert len(context) == _SUMMARY_RETAIN_RECENT
    assert all(isinstance(m, (HumanMessage, AIMessage)) for m in context)
    assert context[0].content == "question 1"  # oldest in window = message 2 (index 2)


def test_load_includes_most_recent_summary_only():
    msgs = _conversation(4)
    msgs.append(SystemMessage(content=f"{_SUMMARY_PREFIX}\nold summary"))
    msgs.append(SystemMessage(content=f"{_SUMMARY_PREFIX}\nnew summary"))
    msgs.append(HumanMessage(content="question 4"))
    msgs.append(AIMessage(content="answer 4"))
    out = load_memory_node({"messages": msgs}, _config())
    context = out["context_messages"]
    assert len(context) == _SUMMARY_RETAIN_RECENT + 1
    assert isinstance(context[0], SystemMessage)
    assert "new summary" in context[0].content
    assert "old summary" not in context[0].content


def test_load_drops_scratch_system_messages():
    msgs = _conversation(2)
    msgs.insert(0, SystemMessage(content="--- CONTEXT ---"))
    out = load_memory_node({"messages": msgs}, _config())
    context = out["context_messages"]
    assert all(isinstance(m, (HumanMessage, AIMessage)) for m in context)


# ── save_memory_node ──────────────────────────────────────────────────────────

def test_save_noop_below_trigger():
    state = {"messages": _conversation(5)}  # 10 messages <= 12
    out = save_memory_node(state, _config())
    assert out == {}


def test_save_fires_above_trigger_and_preserves_recent():
    state = {"messages": _conversation(7)}  # 14 messages > 12
    import langchain_google_genai as lgg

    captured = {}

    def fake_llm(prompt_messages):
        captured["prompt"] = prompt_messages
        return AIMessage(content="test summary")

    class FakeLLM:
        def __init__(self, **kwargs):
            self._invoke = fake_llm

        def invoke(self, prompt_messages):
            return self._invoke(prompt_messages)

    original = lgg.ChatGoogleGenerativeAI
    lgg.ChatGoogleGenerativeAI = FakeLLM  # type: ignore[assignment]
    try:
        out = save_memory_node(state, _config())
    finally:
        lgg.ChatGoogleGenerativeAI = original

    # P3.6: summarised messages are removed (RemoveMessage) + one summary record.
    removals = [m for m in out["messages"] if isinstance(m, RemoveMessage)]
    summaries = [m for m in out["messages"] if isinstance(m, SystemMessage)]
    assert len(removals) == 8        # 14 messages - 6 recent = 8 old ones removed
    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.content.startswith(_SUMMARY_PREFIX)
    assert "test summary" in summary.content

    # RemoveMessages must target the OLD messages, not the recent ones.
    old_ids = {m.id for m in state["messages"][:8]}
    removal_ids = {rm.id for rm in removals}
    assert removal_ids == old_ids

    # The summary prompt must contain the oldest turns but not the recent ones
    prompt_text = captured["prompt"][1].content
    assert "question 0" in prompt_text
    assert "question 6" not in prompt_text  # newest turn is in the recent window


# ── P3.6: token/char budget window ────────────────────────────────────────────

def test_recent_window_short_messages_keeps_fixed_count():
    turns = [HumanMessage(content=f"q {i}") for i in range(20)]
    window = _recent_window(turns)
    assert len(window) == _SUMMARY_RETAIN_RECENT
    assert window[0].content == "q 14"


def test_recent_window_long_message_shrinks_window():
    # One huge message must shrink the retained window well below the fixed count.
    turns = [
        HumanMessage(content="x" * 4000),
        HumanMessage(content="y" * 4000),
        HumanMessage(content="z" * 4000),
    ]
    window = _recent_window(turns)
    assert len(window) < _SUMMARY_RETAIN_RECENT
    assert len(window) >= 1
    assert window[-1].content == "z" * 4000  # newest always kept


def test_recent_window_keeps_at_least_newest():
    turns = [HumanMessage(content="a" * 99999)]
    window = _recent_window(turns)
    assert len(window) == 1
    assert window[0].content == "a" * 99999


def test_load_window_respects_char_budget():
    msgs = []
    for i in range(4):
        msgs.append(HumanMessage(content="short q"))
        msgs.append(AIMessage(content="a" * 3000))
    out = load_memory_node({"messages": msgs}, _config())
    context = out["context_messages"]
    # 3000-char answers barely fit twice in the 8000-char budget, so far fewer
    # than _SUMMARY_RETAIN_RECENT messages are retained.
    assert len(context) < _SUMMARY_RETAIN_RECENT
    assert context[-1].content == "a" * 3000


def test_save_does_not_resummarise_same_content():
    """A second run (same transcript) must not fire again: only turns AFTER
    the last summary count toward the trigger."""
    msgs = _conversation(7)
    msgs.append(SystemMessage(content=f"{_SUMMARY_PREFIX}\nAlready summarized"))
    msgs.append(HumanMessage(content="question 7"))
    msgs.append(AIMessage(content="answer 7"))
    state = {"messages": msgs}
    out = save_memory_node(state, _config())
    assert out == {}  # only 2 new turns since the summary


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
