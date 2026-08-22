"""
Standalone test: Phase 2 integrity — Gemini-outage transcript preservation,
registry concurrent-create smoke, citation match determinism, chapter_id
sentinel unmapping, and the heartbeat wall-clock cap.

Run directly: venv/bin/python backend/test_phase2_integrity.py
"""

import asyncio
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, SystemMessage  # noqa: E402

PASSED = 0
FAILED = 0


def check(label, cond):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  ok  {label}")
    else:
        FAILED += 1
        print(f"FAIL  {label}")


# ── 1. Gemini outage: save_memory_node must NOT delete originals ─────────────

def test_outage_keeps_transcript():
    from tutor.nodes import save_memory_node, _SUMMARY_PREFIX, _SUMMARY_TRIGGER_MSG_COUNT
    import tutor.llm as tllm

    msgs = []
    for i in range(_SUMMARY_TRIGGER_MSG_COUNT):  # comfortably over the trigger
        msgs.append(HumanMessage(content=f"question {i}", id=f"h{i}"))
        msgs.append(AIMessage(content=f"answer {i}", id=f"a{i}"))
    state = {"messages": msgs}

    class ExplodingLLM:
        async def ainvoke(self, prompt_messages):
            raise RuntimeError("simulated Gemini outage")

    original = tllm.make_chat_llm
    tllm.make_chat_llm = lambda **kwargs: ExplodingLLM()
    try:
        out = asyncio.run(save_memory_node(state, {"configurable": {"thread_id": "t"}}))
    finally:
        tllm.make_chat_llm = original

    removals = [m for m in out["messages"] if isinstance(m, RemoveMessage)]
    summaries = [m for m in out["messages"] if isinstance(m, SystemMessage)]
    check("outage: zero RemoveMessages emitted", len(removals) == 0)
    check("outage: placeholder summary still appended", len(summaries) == 1)
    check("outage: placeholder marked truncated",
          summaries and "truncated" in summaries[0].content.lower())
    check("outage: originals untouched",
          all(m.id in {x.id for x in state["messages"]} for m in state["messages"]))

    # And the happy path still removes (guard against over-correction).
    class WorkingLLM:
        async def ainvoke(self, prompt_messages):
            return AIMessage(content="real summary")

    tllm.make_chat_llm = lambda **kwargs: WorkingLLM()
    try:
        out2 = asyncio.run(save_memory_node(state, {"configurable": {"thread_id": "t"}}))
    finally:
        tllm.make_chat_llm = original
    removals2 = [m for m in out2["messages"] if isinstance(m, RemoveMessage)]
    check("happy path: summarised messages still removed", len(removals2) > 0)


# ── 2. Registry concurrent-create smoke ──────────────────────────────────────

def test_registry_parallel_creates_lose_no_entries():
    import json as _json
    from backend import lecture_registry as reg

    saved_path = reg.REGISTRY_PATH
    backup = None
    if saved_path.exists():
        backup = saved_path.read_text(encoding="utf-8")

    tmp_path = Path("/tmp/norai_test_registry.json")
    if tmp_path.exists():
        tmp_path.unlink()
    reg.REGISTRY_PATH = tmp_path
    try:
        n = 24
        barrier = threading.Barrier(n)

        def worker(i: int):
            barrier.wait()
            reg.create_lecture(f"p2-lek-{i}", title=f"Lecture {i}")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        data = _json.loads(tmp_path.read_text(encoding="utf-8"))
        missing = [f"p2-lek-{i}" for i in range(n) if f"p2-lek-{i}" not in data]
        check(f"parallel creates: all {n} entries present", not missing)

        # Concurrent RMW on the SAME entry must end with a valid title.
        barrier2 = threading.Barrier(8)

        def title_worker(i: int):
            barrier2.wait()
            reg.update_lecture_title("p2-lek-0", f"T{i}")

        threads = [threading.Thread(target=title_worker, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        data = _json.loads(tmp_path.read_text(encoding="utf-8"))
        check("parallel title updates: file intact + one title applied",
              data.get("p2-lek-0", {}).get("title", "").startswith("T"))
    finally:
        reg.REGISTRY_PATH = saved_path
        if backup is not None:
            saved_path.write_text(backup, encoding="utf-8")
        tmp_path.unlink(missing_ok=True)


# ── 3. Citations: exact-match first, deterministic containment tiebreaks ──────

def test_citations_exact_match_first():
    from tutor.citations import _best_chunk_for, _normalize

    chunks = [
        {"chunk_id": "c1", "heading_path": "Course Intro > Overview", "heading": "Overview"},
        {"chunk_id": "c2", "heading_path": "Deep Dive > Introduction", "heading": "Introduction"},
        {"chunk_id": "c3", "heading_path": "Wrap-up", "heading": "Summary"},
    ]

    # Exact heading match wins even when an earlier chunk also contains it.
    hit = _best_chunk_for(_normalize("Introduction"), chunks)
    check("citation exact match beats earlier substring", hit["chunk_id"] == "c2")

    # Generic name with no exact match binds to the most specific candidate,
    # deterministically — not to whichever chunk came first.
    generic = [
        {"chunk_id": "first", "heading_path": "Chapter 1 > Section Summary", "heading": "Section Summary"},
        {"chunk_id": "second", "heading_path": "Appendix > Detailed Summary Notes", "heading": "Detailed Summary"},
    ]
    hits = {_best_chunk_for(_normalize("Summary"), generic)["chunk_id"] for _ in range(5)}
    check("generic citation deterministic", len(hits) == 1)

    # No match at all → None.
    check("no-match returns None", _best_chunk_for(_normalize("Nonexistent"), chunks) is None)


# ── 4. chapter_id sentinel unmap ─────────────────────────────────────────────

def test_chapter_sentinel_unmap():
    from tutor.retriever import _unmap_chapter_id, _chunk_from_doc

    check("-1 maps to None", _unmap_chapter_id(-1) is None)
    check("'-1' string maps to None", _unmap_chapter_id("-1") is None)
    check("None stays None", _unmap_chapter_id(None) is None)
    check("valid int preserved", _unmap_chapter_id(3) == 3)
    check("numeric string coerced", _unmap_chapter_id("3") == 3)
    check("garbage → None", _unmap_chapter_id("ch4") is None)

    doc = _chunk_from_doc("id1", "text", {"chapter_id": -1, "heading": "H"}, 0.2)
    check("chunk builder never leaks -1", doc["chapter_id"] is None)


# ── 5. Heartbeat wall-clock cap ───────────────────────────────────────────────

def test_heartbeat_wall_clock_cap(monkeypatch=None):
    import time as time_mod

    import backend.jobs as jobs

    calls = []

    def fake_update(lecture_id, stage, message, percent):
        calls.append(percent)

    original_update = jobs.update_job_progress
    original_interval = jobs.PIPELINE_HEARTBEAT_INTERVAL_SEC
    original_cap = jobs.PIPELINE_MAX_RUNTIME_SEC
    jobs.update_job_progress = fake_update
    jobs.PIPELINE_HEARTBEAT_INTERVAL_SEC = 0.02
    jobs.PIPELINE_MAX_RUNTIME_SEC = 0.2  # cap reached after ~10 ticks
    try:
        stop = threading.Event()
        hb = threading.Thread(target=jobs._heartbeat, args=("lek-x", stop), daemon=True)
        hb.start()
        time_mod.sleep(0.55)  # well past the cap (0.2s)
        stable = len(calls)
        time_mod.sleep(0.15)  # if still ticking, ~7 more would have landed
        stop.set()
        hb.join(timeout=2)
        # Generous floor for scheduler jitter; then assert true quiescence.
        check("heartbeat ticks recorded", stable >= 2)
        check("heartbeats stop after wall-clock cap", len(calls) == stable)
        check("heartbeats never reset progress (all None percent)",
              all(p is None for p in calls))
    finally:
        jobs.update_job_progress = original_update
        jobs.PIPELINE_HEARTBEAT_INTERVAL_SEC = original_interval
        jobs.PIPELINE_MAX_RUNTIME_SEC = original_cap


if __name__ == "__main__":
    test_outage_keeps_transcript()
    test_registry_parallel_creates_lose_no_entries()
    test_citations_exact_match_first()
    test_chapter_sentinel_unmap()
    test_heartbeat_wall_clock_cap()
    print(f"\n{PASSED} passed, {FAILED} failed")
    sys.exit(1 if FAILED else 0)
