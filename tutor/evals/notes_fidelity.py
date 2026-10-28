"""
notes_fidelity.py — how faithful a lecture's study notes are to what was said.

One judge call per lecture: the full timestamped transcript + every chapter's
notes. Per chapter the judge counts the notes' factual claims, lists the ones
the transcript does not support (outside material presented as lecture
content), and lists key points the lecturer made that the notes leave out.
Used to A/B the legacy and lean pipelines on the same lecture.

Usage:
    venv/bin/python -m tutor.evals.notes_fidelity outputs/<lecture> [outputs/<other> ...]
Writes tutor/evals/results/notes_fidelity__<dir-name>.json and prints a summary row
per lecture. Judge model: NORAI_EVAL_JUDGE (default as in answer_eval).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pydantic import BaseModel

from tutor.evals.answer_eval import JUDGE_MODEL, RESULTS_DIR
from tutor.evals.make_questions import load_transcript, transcript_text


class _ChapterGrade(BaseModel):
    chapter_id: int
    total_claims: int
    unsupported_claims: list[str]
    missing_key_points: list[str]


class _Grades(BaseModel):
    chapters: list[_ChapterGrade]


_PROMPT = """\
You audit AI-written study notes against the lecture they were made from. The full
timestamped transcript is the ground truth. For EACH chapter of notes below:

- total_claims: how many distinct factual claims the chapter's notes make
  (definitions, statements, formulas, numbers, examples, attributions).
- unsupported_claims: every claim that the transcript does NOT support: facts,
  formulas, terminology, examples, applications or history the lecturer never gave.
  Quote or closely paraphrase the claim. Rewording or rendering spoken math as notation
  is fine; only flag content that is not in the lecture.
- missing_key_points: important points the lecturer makes in that chapter's part of
  the lecture that the notes leave out (at most 8, most important first).

TRANSCRIPT:
{transcript}

NOTES:
{notes}
"""


def _notes(lecture_dir: Path) -> str:
    files = sorted((lecture_dir / "notes").glob("chapter_*.md"), key=lambda p: int(p.stem.split("_")[1]))
    return "\n\n".join(f"=== chapter_id={p.stem.split('_')[1]} ===\n{p.read_text(encoding='utf-8')}" for p in files)


def judge_notes(lecture_dir: Path) -> dict:
    from google.genai import types
    from backend.gemini_client import get_client, invoke_with_policy
    from backend.usage_ledger import record_generate_usage

    notes = _notes(lecture_dir)
    prompt = _PROMPT.format(transcript=transcript_text(load_transcript(lecture_dir)), notes=notes)

    def _call():
        resp = get_client().models.generate_content(
            model=JUDGE_MODEL,
            contents=prompt,
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
    chapters = [g.model_dump() for g in grades.chapters]
    total = sum(c["total_claims"] for c in chapters)
    unsupported = sum(len(c["unsupported_claims"]) for c in chapters)
    return {
        "lecture_dir": str(lecture_dir),
        "judge": JUDGE_MODEL,
        "summary": {
            "chapters": len(chapters),
            "notes_words": len(notes.split()),
            "claims": total,
            "unsupported": unsupported,
            "unsupported_rate": round(unsupported / total, 3) if total else None,
            "missing_key_points": sum(len(c["missing_key_points"]) for c in chapters),
        },
        "chapters": chapters,
    }


def main() -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    for d in sys.argv[1:]:
        lecture_dir = Path(d)
        result = judge_notes(lecture_dir)
        out = RESULTS_DIR / f"notes_fidelity__{lecture_dir.name}.json"
        out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps({"lecture": lecture_dir.name, **result["summary"]}))


if __name__ == "__main__":
    main()
