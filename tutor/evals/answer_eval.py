"""
answer_eval.py — end-to-end answer-quality eval for the tutor.

Runs every question of a transcript-grounded set (make_questions.py) through
the REAL tutor graph in-process (fresh in-memory thread per question, so no
lecture checkpoints are touched), then grades all answers against the full
transcript in one batched judge call on a stronger model.

Metrics per category:
  core/detail    — accuracy (correct=1, partial=0.5), false "not covered" rate
  out_of_scope   — honest abstention rate (says the lecture doesn't cover it)
  false_premise  — premise corrected rate
  all            — unsupported-lecture-claim rate (attributes to the lecture
                   something the transcript doesn't say), invented-visual rate,
                   citation stats, latency, tokens

Usage:
    venv/bin/python -m tutor.evals.answer_eval --set calc17 --label baseline
    venv/bin/python -m tutor.evals.answer_eval --set hi_search --field question_hi --label local
Writes tutor/evals/results/<set>__<label>.json and prints a summary row.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import time
import uuid
from pathlib import Path

from pydantic import BaseModel

from tutor.evals.make_questions import DATA_DIR, load_transcript, transcript_text

RESULTS_DIR = Path(__file__).parent / "results"
JUDGE_MODEL = os.environ.get("NORAI_EVAL_JUDGE", "gemini-3.8-flash")


# ── Running the tutor ─────────────────────────────────────────────────────────

def _lecture_title(lecture_dir: Path) -> str:
    try:
        o = json.loads((lecture_dir / "notes" / "lecture_outline.json").read_text())
        return o.get("lecture_title", "")
    except Exception:
        return ""


async def run_tutor(lecture_dir: Path, questions: list[dict], gap_s: float) -> list[dict]:
    from langgraph.checkpoint.memory import InMemorySaver

    from backend.usage_ledger import diff_usage, snapshot_usage
    from tutor.graph import build_graph

    graph = build_graph(InMemorySaver(), output_dir=str(lecture_dir))
    title = _lecture_title(lecture_dir)
    rows = []
    for i, q in enumerate(questions, 1):
        before = snapshot_usage()
        t0 = time.perf_counter()
        tid = f"eval-{uuid.uuid4().hex[:8]}"
        state = await graph.ainvoke(
            {
                "thread_id": tid,
                "user_question": q["question"],
                "message_id": uuid.uuid4().hex,
                "study_mode": "default",
                "persona_instructions": "",
                "lecture_title": title,
            },
            {"configurable": {"thread_id": tid}},
        )
        latency = time.perf_counter() - t0
        usage = diff_usage(before)
        rows.append({
            **q,
            "answer": state.get("answer", ""),
            "latency_s": round(latency, 2),
            "calls": sum(u.get("calls", 0) for u in usage),
            "input_tokens": sum(u.get("input_tokens", 0) for u in usage),
            "output_tokens": sum(u.get("output_tokens", 0) for u in usage),
            "cost_usd": round(sum(u.get("cost_usd", 0.0) for u in usage), 6),
            "retrieval_status": state.get("retrieval_status"),
            "retrieved": [
                {
                    "heading_path": c.get("heading_path"),
                    "chapter_id": c.get("chapter_id"),
                    "distance": c.get("distance"),
                    "start": c.get("start"),
                }
                for c in state.get("retrieved_chunks", [])
            ],
            "images": [
                {"section": im.get("section"), "distance": im.get("distance")}
                for im in state.get("retrieved_images", [])
            ],
            "citations": state.get("verified_citations", []),
        })
        print(f"  [{i}/{len(questions)}] {latency:5.1f}s {q['category']:13s} {q['question'][:70]}")
        if gap_s:
            await asyncio.sleep(gap_s)
    return rows


# ── Judging ───────────────────────────────────────────────────────────────────

class _Grade(BaseModel):
    id: int
    verdict: str                 # correct | partial | incorrect
    says_not_covered: bool       # answer claims the lecture doesn't cover/address it
    unsupported_lecture_claim: bool
    corrected_premise: bool
    invented_visual: bool
    note: str


class _Grades(BaseModel):
    grades: list[_Grade]


_JUDGE_PROMPT = """\
You grade an AI tutor that must answer students ONLY from one lecture, whose full
timestamped transcript is below. For each item you get the question, its category,
a reference answer, and the tutor's answer. Grade strictly against the TRANSCRIPT.

Fields:
- verdict: "correct" if the tutor's answer conveys the reference answer's key point
  accurately; "partial" if it is incomplete or vague but not wrong; "incorrect" if it is
  wrong, misses the point, or (for in-lecture questions) refuses. For out_of_scope items,
  "correct" means it clearly says the lecture does not cover it (general-knowledge help
  after that is fine). For false_premise items, "correct" means it rejects the false premise.
- says_not_covered: true if the answer states or implies the lecture/material does not
  cover or address the question.
- unsupported_lecture_claim: true if the answer attributes to the lecture (e.g. "the
  lecture says/shows", "as the lecturer explains", or presents as lecture content) any
  specific claim that is NOT in the transcript. General knowledge clearly labelled as
  such does not count.
- corrected_premise: true if the answer explicitly corrects a false assumption in the question.
- invented_visual: true if the answer describes a slide, diagram, screenshot or visual
  as if seen, with specifics not supported by the transcript.
- note: one short sentence explaining the verdict.

TRANSCRIPT:
{transcript}

ITEMS:
{items}
"""


def judge(lecture_dir: Path, rows: list[dict]) -> list[dict]:
    from google.genai import types
    from backend.gemini_client import get_client, invoke_with_policy
    from backend.usage_ledger import record_generate_usage

    segments = load_transcript(lecture_dir)
    items = "\n\n".join(
        f"### id={i}\ncategory: {r['category']}\nquestion: {r['question']}\n"
        f"reference: {r['gold_answer']}\ntutor_answer:\n{r['answer']}"
        for i, r in enumerate(rows)
    )
    client = get_client()

    def _call():
        resp = client.models.generate_content(
            model=JUDGE_MODEL,
            contents=_JUDGE_PROMPT.format(transcript=transcript_text(segments), items=items),
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
                response_schema=_Grades,
                http_options=types.HttpOptions(timeout=240_000),
            ),
        )
        record_generate_usage("eval_judge", JUDGE_MODEL, resp)
        return _Grades.model_validate_json(resp.text)

    grades = invoke_with_policy(_call, node="eval_judge", max_retries=4, rate_limited=False)
    by_id = {g.id: g.model_dump() for g in grades.grades}
    for i, r in enumerate(rows):
        r["grade"] = by_id.get(i)
    return rows


# ── Scoring ───────────────────────────────────────────────────────────────────

_SCORE = {"correct": 1.0, "partial": 0.5, "incorrect": 0.0}


def summarize(rows: list[dict]) -> dict:
    graded = [r for r in rows if r.get("grade")]

    def frac(sub, pred):
        return round(sum(1 for r in sub if pred(r)) / len(sub), 3) if sub else None

    in_lec = [r for r in graded if r["category"] in ("core", "detail")]
    out = {
        "n": len(rows),
        "graded": len(graded),
        "accuracy_core": None,
        "accuracy_detail": None,
        "false_not_covered": frac(in_lec, lambda r: r["grade"]["says_not_covered"]),
        "oos_abstain": frac(
            [r for r in graded if r["category"] == "out_of_scope"],
            lambda r: r["grade"]["says_not_covered"],
        ),
        "premise_corrected": frac(
            [r for r in graded if r["category"] == "false_premise"],
            lambda r: r["grade"]["verdict"] == "correct",
        ),
        "unsupported_claim": frac(graded, lambda r: r["grade"]["unsupported_lecture_claim"]),
        "invented_visual": frac(graded, lambda r: r["grade"]["invented_visual"]),
        "answers_citing": frac(rows, lambda r: bool(r["citations"])),
        "citations_verified": None,
        "latency_p50_s": round(statistics.median(r["latency_s"] for r in rows), 2),
        "calls_per_turn": round(statistics.mean(r["calls"] for r in rows), 2),
        "input_tokens_per_turn": round(statistics.mean(r["input_tokens"] for r in rows)),
        "output_tokens_per_turn": round(statistics.mean(r["output_tokens"] for r in rows)),
        "cost_per_turn_usd": round(statistics.mean(r["cost_usd"] for r in rows), 6),
    }
    for cat in ("core", "detail"):
        sub = [r for r in graded if r["category"] == cat]
        if sub:
            out[f"accuracy_{cat}"] = round(
                sum(_SCORE.get(r["grade"]["verdict"], 0) for r in sub) / len(sub), 3
            )
    cits = [c for r in rows for c in r["citations"]]
    if cits:
        out["citations_verified"] = round(sum(1 for c in cits if c.get("verified")) / len(cits), 3)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", required=True, help="question set name under tutor/evals/data/")
    ap.add_argument("--label", required=True)
    ap.add_argument("--lecture-dir", help="override the set's lecture dir")
    ap.add_argument("--gap", type=float, default=2.0, help="seconds between questions")
    ap.add_argument("--rejudge", action="store_true", help="re-grade an existing result file")
    ap.add_argument("--no-judge", action="store_true", help="only collect answers")
    ap.add_argument("--field", default="question",
                    help="question field to ask, e.g. question_hi (romanized Hinglish rewrite)")
    args = ap.parse_args()

    qset = json.loads((DATA_DIR / f"{args.set}.json").read_text())
    lecture_dir = Path(args.lecture_dir or qset["lecture_dir"])
    RESULTS_DIR.mkdir(exist_ok=True)
    out_path = RESULTS_DIR / f"{args.set}__{args.label}.json"

    if args.rejudge:
        rows = json.loads(out_path.read_text())["rows"]
    else:
        questions = qset["questions"]
        if args.field != "question":
            questions = [{**q, "question": q[args.field], "question_en": q["question"]}
                         for q in questions]
        rows = asyncio.run(run_tutor(lecture_dir, questions, args.gap))
        # Persist answers first: a judge failure (quota) must not lose them.
        out_path.write_text(json.dumps({"summary": None, "rows": rows}, indent=2, ensure_ascii=False))
        if args.no_judge:
            return
    rows = judge(lecture_dir, rows)
    summary = summarize(rows)
    out_path.write_text(json.dumps({"summary": summary, "rows": rows}, indent=2, ensure_ascii=False))
    print(json.dumps({"set": args.set, "label": args.label, **summary}))


if __name__ == "__main__":
    main()
