"""
make_questions.py — build a transcript-grounded question set for one lecture.

The older golden sets (golden_sets.py) score retrieval against note headings,
so they can only tell whether the tutor found the right *note*. This set is
grounded in what the lecturer actually said: every in-lecture question carries
a verbatim transcript quote, checked here against the transcript, so the
answer eval (answer_eval.py) can grade answers against the lecture itself.

Categories:
  core          — a main idea of the lecture
  detail        — a specific example, number, name or aside said in passing
  out_of_scope  — on-topic for the subject but NOT covered by this lecture
  false_premise — asserts something the lecture contradicts

One Gemini call per lecture. Usage:
    venv/bin/python -m tutor.evals.make_questions --lecture-dir outputs/<id> --name calc17
Writes tutor/evals/data/<name>.json.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from pydantic import BaseModel

DATA_DIR = Path(__file__).parent / "data"


class _Q(BaseModel):
    category: str
    question: str
    gold_answer: str
    quote: str


class _QSet(BaseModel):
    questions: list[_Q]


_PROMPT = """\
You are writing an exam to test whether an AI tutor answers faithfully from ONE lecture.
Below is the full timestamped transcript. Write exactly:
- 8 "core" questions about the lecture's main ideas,
- 8 "detail" questions about specific examples, numbers, names, analogies or asides the
  lecturer mentions only briefly (the kind a summary would drop),
- 4 "out_of_scope" questions a student of this subject might plausibly ask that this
  lecture does NOT answer (do not pick anything the lecturer even mentions),
- 3 "false_premise" questions that presuppose something the lecture contradicts.

Rules:
- Phrase questions the way a student would, without saying "according to the lecture".
- gold_answer: 1-2 sentences, what a faithful tutor should say. For out_of_scope, say what is
  missing. For false_premise, state the correction.
- quote: a VERBATIM span (8-40 words) copied exactly from the transcript text that supports
  the gold answer. For out_of_scope use an empty string.

TRANSCRIPT:
{transcript}
"""


def load_transcript(lecture_dir: Path) -> list[dict]:
    files = sorted((lecture_dir / "transcripts").glob("*.json"))
    if not files:
        raise SystemExit(f"no transcript json under {lecture_dir}/transcripts")
    return json.loads(files[0].read_text(encoding="utf-8"))["segments"]


def fmt_ts(sec: float) -> str:
    sec = int(sec)
    return f"{sec // 60}:{sec % 60:02d}"


def transcript_text(segments: list[dict]) -> str:
    return "\n".join(f"[{fmt_ts(s['start'])}] {s['text'].strip()}" for s in segments)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def locate_quote(quote: str, segments: list[dict]) -> float | None:
    """Start time of the segment where `quote` begins, or None if the quote is
    not verbatim (modulo punctuation/case) in the transcript."""
    q = _norm(quote)
    if not q:
        return None
    full, starts = "", []
    for s in segments:
        starts.append((len(full), s["start"]))
        full += _norm(s["text"]) + " "
    pos = full.find(q)
    if pos < 0:
        return None
    t = segments[0]["start"]
    for offset, start in starts:
        if offset > pos:
            break
        t = start
    return t


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lecture-dir", required=True)
    ap.add_argument("--name", required=True)
    args = ap.parse_args()

    from google.genai import types
    from backend.gemini_client import get_client, invoke_with_policy
    from backend.usage_ledger import record_generate_usage
    from config import MODEL_NAME

    lecture_dir = Path(args.lecture_dir)
    segments = load_transcript(lecture_dir)
    client = get_client()

    def _call():
        r = client.models.generate_content(
            model=MODEL_NAME,
            contents=_PROMPT.format(transcript=transcript_text(segments)),
            config=types.GenerateContentConfig(
                temperature=0.3,
                response_mime_type="application/json",
                response_schema=_QSet,
            ),
        )
        record_generate_usage("eval_questions", MODEL_NAME, r)
        return _QSet.model_validate_json(r.text)

    qset = invoke_with_policy(_call, node="eval_questions", max_retries=3)

    kept, dropped = [], []
    for q in qset.questions:
        item = q.model_dump()
        if q.category != "out_of_scope":
            t = locate_quote(q.quote, segments)
            if t is None:
                dropped.append(item)
                continue
            item["quote_ts"] = t
        kept.append(item)

    DATA_DIR.mkdir(exist_ok=True)
    out = DATA_DIR / f"{args.name}.json"
    out.write_text(json.dumps({
        "lecture_dir": str(lecture_dir),
        "questions": kept,
        "dropped_unverified": dropped,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {out}: {len(kept)} kept, {len(dropped)} dropped (quote not verbatim)")


if __name__ == "__main__":
    main()
