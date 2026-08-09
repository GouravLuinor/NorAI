"""
runner.py — P3.1 golden-QA retrieval eval runner.

Retrieval-only (no LLM): for each hand-authored golden question, queries the
lecture's Chroma index and scores MRR / hit-rate@k / distance stats, plus a
reference-gate simulation that mirrors P3.8 (only strong matches surface as
references).

Usage:
    venv/bin/python -m tutor.evals.runner --lecture 6ddb64c1-e42d-40c4-b99e-22b469d76f07
    venv/bin/python -m tutor.evals.runner --lecture <id> --top-k 10 --threshold-sweep

NOTE: this makes one embedding API call per golden question (~15 calls for the
seeded lecture). Offline metric math lives in evals/metrics.py and is tested by
tutor/evals/test_evals.py without any API calls.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from tutor.retrieval_config import TOP_K
from tutor.evals.metrics import (
    evaluate_questions,
    first_gold_rank,
    threshold_sweep,
)
from tutor.evals.golden_sets import get_golden_set

_THRESHOLD_SWEEP_STEPS = [round(0.20 + 0.05 * i, 2) for i in range(9)]  # 0.20..0.60


def _default_output_dir(lecture_id: str) -> Path:
    return Path("outputs") / lecture_id


def run_eval(lecture_id: str, output_dir: str, top_k: int, sweep: bool) -> dict:
    from tutor.retriever import IndexNotBuiltError, retrieve

    golden = get_golden_set(lecture_id)
    if golden is None:
        raise SystemExit(
            f"No golden set authored for lecture '{lecture_id}'. "
            f"Add one to tutor/evals/golden_sets.py first."
        )

    out = Path(output_dir)
    questions = []
    errors = 0
    for i, item in enumerate(golden["questions"], 1):
        q = item["q"]
        try:
            chunks = retrieve(query=q, k=top_k, output_dir=str(out))
            print(f"  [{i}/{len(golden['questions'])}] retrieved {len(chunks)} for: {q[:60]!r}")
        except IndexNotBuiltError as exc:
            print(f"  [{i}/{len(golden['questions'])}] ERROR: {exc}")
            chunks = []
            errors += 1
        questions.append({"q": q, "gold": item["gold"], "retrieved": chunks})

    summary = evaluate_questions(questions, top_k, threshold=_THRESHOLD_SWEEP_STEPS[0])
    sweep_rows, recommended = threshold_sweep(questions, top_k, _THRESHOLD_SWEEP_STEPS)

    report = {
        "lecture_id": lecture_id,
        "title": golden["title"],
        "run_at": datetime.now(timezone.utc).isoformat(),
        "top_k": top_k,
        "errors": errors,
        "summary": summary,
        "threshold_recommendation": recommended if sweep else None,
        "threshold_sweep": sweep_rows if sweep else [],
        "questions": [
            {
                "q": q["q"],
                "gold": q["gold"],
                "first_gold_rank": first_gold_rank(q["retrieved"], q["gold"]),
                "distances": [round(c.get("distance", 1.0), 4) for c in q["retrieved"]],
                "sections": [
                    {"heading_path": c.get("heading_path"), "distance": round(c.get("distance", 1.0), 4)}
                    for c in q["retrieved"]
                ],
            }
            for q in questions
        ],
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="P3.1 golden-QA retrieval eval")
    parser.add_argument("--lecture", required=True, help="lecture id (outputs/<id>/notes)")
    parser.add_argument("--output-dir", default=None, help="lecture output dir (default outputs/<lecture>)")
    parser.add_argument("--top-k", type=int, default=TOP_K)
    parser.add_argument("--threshold-sweep", action="store_true", help="calibrate CONFIDENCE_THRESHOLD")
    args = parser.parse_args()

    output_dir = args.output_dir or str(_default_output_dir(args.lecture))
    print(f"Running golden-QA eval for lecture {args.lecture} (top_k={args.top_k})...")
    report = run_eval(args.lecture, output_dir, args.top_k, args.threshold_sweep)

    s = report["summary"]
    print("\n── Summary ──")
    print(f"  questions        : {s['questions']}")
    print(f"  hit_rate@{s['top_k']} : {s['hit_rate']}")
    print(f"  MRR@{s['top_k']}      : {s['mrr']}")
    print(f"  mean hit dist    : {s['mean_hit_distance']}")
    print(f"  mean miss dist   : {s['mean_miss_distance']}")
    print(f"  [P3.8 gate] mean strong matches/question: {s['mean_strong_count']}")
    print(f"  [P3.8 gate] questions showing 0 references: {s['zero_strong_fraction']:.0%}")

    if args.threshold_sweep and report["threshold_sweep"]:
        print("\n── Confidence threshold sweep ──")
        print(f"  {'thr':<6}{'precision':<10}{'gold_recall':<12}{'f1':<8}{'0-refs':<8}")
        for row in report["threshold_sweep"]:
            p = row["strong_precision"]
            r = row["gold_strong_recall"]
            print(
                f"  {row['threshold']:<6.2f}"
                f"{'-' if p is None else round(p, 3):<10}"
                f"{'-' if r is None else round(r, 3):<12}"
                f"{row['f1']:<8.4f}"
                f"{row['zero_strong_fraction']:<8.3f}"
            )
        print(f"\n  Recommended CONFIDENCE_THRESHOLD: {report['threshold_recommendation']}")

    reports_dir = Path("outputs") / "evals"
    reports_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    path = reports_dir / f"retrieval_{args.lecture}_{ts}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nReport written: {path}")


if __name__ == "__main__":
    sys.exit(main())
