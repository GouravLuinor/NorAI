"""
test_evals.py — Offline unit tests for the P3.1 golden-QA eval metrics.

No Chroma, no Gemini, no embedding API calls — pure math over synthetic
retrieved-chunk dicts.

Run:
    venv/bin/python tutor/evals/test_evals.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tutor.evals.metrics import (  # noqa: E402
    chunk_matches,
    evaluate_questions,
    first_gold_rank,
    hit_rate,
    is_strong,
    mrr,
    threshold_sweep,
)


def _mk(heading_path: str, distance: float, heading: str | None = None) -> dict:
    return {
        "text": "body text",
        "heading": heading or heading_path.split(" > ")[-1],
        "heading_path": heading_path,
        "chapter_id": 1,
        "source": "outputs/x/notes/chapter_1.md",
        "distance": distance,
    }


def test_chunk_matches_substring_path():
    c = _mk("Chapter 4: Mechanics > Core Architecture: The Transformer", 0.21)
    assert chunk_matches(c, ["Core Architecture: The Transformer"])
    assert chunk_matches(c, ["transformer"])  # case-insensitive
    assert not chunk_matches(c, ["Prompt Engineering"])


def test_chunk_matches_leaf_heading():
    c = _mk("Chapter 10: Societal > Practical Applications", 0.3, heading="1. AI as a Sounding Board")
    assert chunk_matches(c, ["AI as a Sounding Board"])
    assert not chunk_matches(c, ["Nothing Here"])


def test_first_gold_rank_zero_and_found():
    chunks = [_mk("A", 0.5), _mk("B", 0.5), _mk("Gold Section", 0.2)]
    assert first_gold_rank(chunks, ["Gold Section"]) == 3
    assert first_gold_rank(chunks, ["Missing"]) == 0


def test_mrr():
    assert mrr([]) == 0.0
    assert mrr([1, 0, 2]) == round((1.0 + 0.0 + 0.5) / 3, 4)


def test_hit_rate():
    assert hit_rate([]) == 0.0
    assert hit_rate([True, False, True]) == round(2 / 3, 4)


def test_is_strong_boundary():
    assert is_strong(_mk("A", 0.35), 0.35)          # at threshold = strong
    assert is_strong(_mk("A", 0.34), 0.35)
    assert not is_strong(_mk("A", 0.36), 0.35)
    assert not is_strong(_mk("A", None), 0.35)      # missing distance = weak


def test_evaluate_questions_aggregates():
    questions = [
        {"q": "q1", "gold": ["Gold A"], "retrieved": [_mk("Gold A", 0.20), _mk("Noise", 0.50)]},
        {"q": "q2", "gold": ["Gold B"], "retrieved": [_mk("Noise", 0.45), _mk("Gold B", 0.60)]},
        {"q": "q3", "gold": ["Gold C"], "retrieved": [_mk("Noise", 0.55)]},
    ]
    s = evaluate_questions(questions, top_k=2, threshold=0.35)
    assert s["questions"] == 3
    assert s["hit_rate"] == round(2 / 3, 4)        # q3's gold chunk was never retrieved
    assert s["mrr"] == round((1.0 + 0.5 + 0.0) / 3, 4)
    assert s["mean_strong_count"] == round(1 / 3, 3)   # only q1's first chunk is strong
    assert s["zero_strong_fraction"] == round(2 / 3, 3)
    assert s["strong_precision"] == 1.0            # the 1 strong chunk is gold
    assert s["gold_strong_recall"] == round(1 / 3, 4)
    assert s["mean_hit_distance"] == round((0.20 + 0.60) / 2, 4)
    assert s["mean_miss_distance"] == round((0.50 + 0.45 + 0.55) / 3, 4)


def test_threshold_sweep_picks_best():
    # Gold chunks sit at distance ~0.25; noise at ~0.6. The sweep should prefer
    # a threshold around 0.25-0.35 (high precision) over 0.5 (noise leaks in).
    questions = []
    for i in range(6):
        questions.append(
            {"q": f"q{i}", "gold": [f"Gold {i}"], "retrieved": [_mk(f"Gold {i}", 0.25), _mk("Noise", 0.6)]}
        )
    rows, recommended = threshold_sweep(questions, top_k=2, thresholds=[0.20, 0.25, 0.30, 0.35, 0.40, 0.50, 0.60])
    assert recommended in (0.25, 0.30, 0.35)
    best = max(rows, key=lambda r: r["f1"])
    assert best["f1"] > 0.9  # clean separation should reach near-perfect F1


def test_golden_sets_schema():
    from tutor.evals.golden_sets import GOLDEN_SETS, get_golden_set
    for lid, gs in GOLDEN_SETS.items():
        assert gs["title"]
        assert len(gs["questions"]) >= 1
        for q in gs["questions"]:
            assert q["q"].strip()
            assert isinstance(q["gold"], list) and q["gold"]
    assert get_golden_set("does-not-exist") is None


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
