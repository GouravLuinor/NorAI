"""
backend/routers/quiz.py — quiz generation, evaluation, and attempt history (P5.1).

Extracted verbatim from main.py; mounted without prefixes so paths are
unchanged.
"""

import json
import logging
import time
import uuid
from pathlib import Path
import json as json_lib
import random
import re
import sqlite3
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from backend.access import ensure_lecture_access
from backend.auth import get_current_user_optional
from backend.db.database import get_db
from backend.db.models import User
from backend.lecture_registry import get_lecture
from backend.lecture_db import (
    _db,
    _ensure_quiz_attempts_table,
    _ensure_quiz_attempts_correct_ids,
)

router = APIRouter()


class QuestionFeedback(BaseModel):
    question_number: int
    remark: str

class QuizEvaluation(BaseModel):
    final_score: int
    total_questions: int
    per_question_feedback: List[QuestionFeedback]
    overall_insights: str

class Question(BaseModel):
    """P5.4: typed contract for quiz questions crossing the API boundary.

    Mirrors the frontend Question interface (useQuizStore). Extra fields are
    tolerated (Pydantic ignores unknown keys) so older clients keep working;
    required fields are validated on the way IN.
    """
    model_config = {"extra": "ignore"}

    id: int
    question: str
    type: str
    answer: str
    explanation: str = ""
    difficulty: str | None = None
    options: list[str] | None = None


class AnsweredQuestion(Question):
    """A Question plus the student's submission (evaluate payload)."""
    user_answer: str = ""


class QuizEvaluateRequest(BaseModel):
    # P5.4: validated objects instead of opaque dicts.
    questions: list[AnsweredQuestion]
    elapsed_seconds: int = 0
    confidences: list[str] = []

class QuizExplainRequest(BaseModel):
    question: str
    lecture_id: str = "default"
    chapter_id: int | None = None

class CreateQuizAttemptRequest(BaseModel):
    lecture_id: str = "default"
    chapter_id: int | None = None
    difficulty: str = "All"
    # P5.4: validated as full Question objects, not opaque dicts.
    questions: list[Question] = []

class FinishQuizAttemptRequest(BaseModel):
    answers: list[dict] = []
    confidences: list[str] = []
    evaluation: dict | None = None
    score: float = 0.0
    total: int = 0
    correct_ids: list[str] = []


@router.get("/quiz/questions")
async def quiz_questions(
    chapter_id: int | None = None,
    n: int = 5,
    lecture_id: str = "default",
    difficulty: str | None = None,
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    await ensure_lecture_access(lecture_id, user, db)
    info = get_lecture(lecture_id)
    base = Path(info["output_dir"]) if info else Path("outputs")
    path = base / "assessment" / f"assessment_chapter_{chapter_id}.json" if chapter_id else base / "assessment" / "assessment.json"
    if not path.exists():
        return {"questions": [], "incomplete": False}
    raw_data = json_lib.loads(path.read_text(encoding="utf-8"))
    incomplete = False
    if isinstance(raw_data, dict):
        questions = raw_data.get("questions", [])
        incomplete = bool(raw_data.get("incomplete", False))
    elif isinstance(raw_data, list):
        questions = raw_data
    else:
        questions = []
    questions = [q for q in questions if isinstance(q, dict)]
    if difficulty:
        norm = difficulty.strip().lower()
        if norm in ("easy", "medium", "hard"):
            questions = [q for q in questions if str(q.get("difficulty", "")).strip().lower() == norm]
    if len(questions) > n:
        questions = random.sample(questions, n)
    return {"questions": questions, "incomplete": incomplete}


@router.post("/quiz/evaluate")
async def quiz_evaluate(req: QuizEvaluateRequest):
    prompt_lines = [
        "You are a tutor evaluating a student's quiz. Below are the questions, the student's answers, and the correct answers.",
        "For each question, decide if the student's answer is essentially correct. Be lenient with wording, spelling, and minor variations.",
        "Then provide a final score and detailed feedback.",
        "",
        "You MUST respond with a JSON object that matches this structure:",
        "{",
        '  "final_score": <number of correct answers>,',
        '  "total_questions": <total number of questions>,',
        '  "per_question_feedback": [',
        '    {"question_number": 1, "remark": "..."},',
        '    {"question_number": 2, "remark": "..."}',
        "  ],",
        '  "overall_insights": "..."',
        "}",
        "",
        "Important: final_score must be the number of correct answers (e.g., 4), NOT a percentage.",
        "Do NOT include any other text.",
        "",
    ]

    if req.elapsed_seconds:
        mins, secs = divmod(req.elapsed_seconds, 60)
        prompt_lines.append(f"Time taken: {mins}m {secs}s.")
    if req.confidences:
        prompt_lines.append("Confidence ratings per question: " + ", ".join(req.confidences))
    prompt_lines.append("")

    for i, q in enumerate(req.questions, 1):
        prompt_lines.append(f"Q{i} ({q.type}): {q.question}")
        if q.options:
            prompt_lines.append(f"Options: {', '.join(q.options)}")
        prompt_lines.append(f"Your answer: {q.user_answer}")
        prompt_lines.append(f"Correct answer: {q.answer}")
        if q.explanation:
            prompt_lines.append(f"Explanation: {q.explanation}")
        prompt_lines.append("")
    prompt_lines.append("Respond with the JSON object now.")

    llm = make_chat_llm(node="quiz_evaluate", temperature=0.2)
    response = llm.invoke([
        SystemMessage(content="You are a helpful tutor. Always respond with valid JSON."),
        HumanMessage(content="\n".join(prompt_lines)),
    ])
    text = response.content
    if isinstance(text, list):
        text = " ".join(
            block["text"] for block in text if isinstance(block, dict) and "text" in block
        )

    try:
        start = text.find('{')
        end   = text.rfind('}') + 1
        if start == -1 or end <= start:
            raise ValueError("No JSON object found in LLM response")
        evaluation = QuizEvaluation(**json_lib.loads(text[start:end]))
        return {
            "evaluation": {
                "final_score": evaluation.final_score,
                "total_questions": evaluation.total_questions,
                "per_question_feedback": [fb.model_dump() for fb in evaluation.per_question_feedback],
                "overall_insights": evaluation.overall_insights,
            }
        }
    except Exception as exc:
        logging.getLogger("norai").exception("POST /quiz/evaluate: LLM output failed to parse; raw output suppressed from response")
        return {
            "evaluation": {
                "final_score": None,
                "total_questions": len(req.questions),
                "per_question_feedback": [],
                "overall_insights": "The evaluation could not be generated. Please try submitting your answers again.",
            }
        }


@router.post("/quiz/explain")
async def quiz_explain(
    req: QuizExplainRequest,
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Cite a question's source from the lecture index — on demand only.

    Runs a single embedding retrieval (top-1 note chunk + top-1 screenshot).
    Never regenerates. Returns source:null gracefully when the index is missing.
    P6.4: read-gated (owner or valid share link; tutor permission NOT required).
    """
    if not req.question.strip():
        return {"source": None, "message": "Empty question."}

    # P6.4: read-only index access — no LLM cost, so require_tutor=False.
    await ensure_lecture_access(req.lecture_id or "default", user, db, require_tutor=False)

    lecture_id = req.lecture_id if req.lecture_id and req.lecture_id != "default" else None
    output_dir = None
    if lecture_id:
        info = get_lecture(lecture_id)
        if info:
            output_dir = info.get("output_dir")

    from tutor.retriever import retrieve, retrieve_images, IndexNotBuiltError

    try:
        chunks = await asyncio.to_thread(
            retrieve,
            req.question.strip(),
            chapter_id=req.chapter_id,
            k=1,
            output_dir=output_dir,
        )
    except IndexNotBuiltError:
        return {"source": None, "message": "No lecture index available for citation."}
    except Exception as exc:
        logging.getLogger("norai").exception("quiz/explain retrieval error")
        return {"source": None, "message": "Could not retrieve a source for this question."}

    top = chunks[0] if chunks else None
    screenshot = None
    if top:
        try:
            images = await asyncio.to_thread(
                retrieve_images,
                req.question.strip(),
                chapter_id=req.chapter_id,
                k=1,
                output_dir=output_dir,
            )
            if images:
                screenshot = images[0].get("path")
        except Exception:
            screenshot = None

    if not top:
        return {"source": None, "message": "No matching source found in the lecture."}

    return {
        "source": top.get("heading_path") or top.get("heading") or "Lecture notes",
        "heading": top.get("heading", ""),
        "heading_path": top.get("heading_path", ""),
        "chapter_id": top.get("chapter_id"),
        "chunk_id": top.get("chunk_id"),
        "text": top.get("text", "")[:400],
        "screenshot": screenshot,
    }


# ---------------------------------------------------------------------------
# Quiz Attempts & Flashcard Persistence Endpoints
# ---------------------------------------------------------------------------

@router.post("/quiz/attempts")
async def create_quiz_attempt(
    req: CreateQuizAttemptRequest,
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    await ensure_lecture_access(req.lecture_id, user, db, require_tutor=True)
    attempt_id = f"attempt-{uuid.uuid4().hex[:12]}"
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with _db(req.lecture_id) as conn:
        _ensure_quiz_attempts_table(conn)
        conn.execute(
            "INSERT INTO quiz_attempts "
            "(id, user_id, lecture_id, chapter_id, difficulty, started_at, finished_at, questions_json, answers_json, confidences_json, evaluation_json, score, total) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                attempt_id,
                str(user.id) if user else "",
                req.lecture_id,
                req.chapter_id,
                req.difficulty,
                now,
                "",
                json_lib.dumps([q.model_dump() for q in req.questions]),
                json_lib.dumps([]),
                json_lib.dumps([]),
                json_lib.dumps({}),
                0.0,
                len(req.questions),
            ),
        )
    return {"attempt_id": attempt_id}


@router.post("/quiz/attempts/{attempt_id}/finish")
async def finish_quiz_attempt(
    attempt_id: str,
    req: FinishQuizAttemptRequest,
    lecture_id: str = "default",
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    await ensure_lecture_access(lecture_id, user, db, require_tutor=True)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with _db(lecture_id) as conn:
        _ensure_quiz_attempts_table(conn)
        _ensure_quiz_attempts_correct_ids(conn)
        cursor = conn.execute(
            "UPDATE quiz_attempts SET finished_at=?, answers_json=?, confidences_json=?, evaluation_json=?, correct_ids_json=?, score=?, total=? "
            "WHERE id=? AND lecture_id=? AND user_id=?",
            (
                now,
                json_lib.dumps(req.answers),
                json_lib.dumps(req.confidences),
                json_lib.dumps(req.evaluation or {}),
                json_lib.dumps(req.correct_ids),
                req.score,
                req.total,
                attempt_id,
                lecture_id,
                str(user.id) if user else "",
            ),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Quiz attempt not found")
    return {"success": True, "attempt_id": attempt_id}



@router.get("/quiz/attempts")
async def list_quiz_attempts(
    lecture_id: str = "default",
    chapter_id: int | None = None,
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    await ensure_lecture_access(lecture_id, user, db)
    attempt_uid = str(user.id) if user else ""
    with _db(lecture_id) as conn:
        _ensure_quiz_attempts_table(conn)
        if chapter_id is not None:
            cursor = conn.execute(
                "SELECT id, lecture_id, chapter_id, difficulty, started_at, finished_at, score, total "
                "FROM quiz_attempts WHERE lecture_id=? AND chapter_id=? AND user_id=? ORDER BY started_at DESC",
                (lecture_id, chapter_id, attempt_uid),
            )
        else:
            cursor = conn.execute(
                "SELECT id, lecture_id, chapter_id, difficulty, started_at, finished_at, score, total "
                "FROM quiz_attempts WHERE lecture_id=? AND user_id=? ORDER BY started_at DESC",
                (lecture_id, attempt_uid),
            )
        rows = cursor.fetchall()
        attempts = [
            {
                "id": r[0],
                "lecture_id": r[1],
                "chapter_id": r[2],
                "difficulty": r[3],
                "started_at": r[4],
                "finished_at": r[5],
                "score": r[6],
                "total": r[7],
            }
            for r in rows
        ]
        return {"attempts": attempts}


_REMARK_NEGATIVE = re.compile(
    r"\b(incorrect|incorrectly|wrong|not correct|mistake|missed|not quite|unfortunately|almost)\b"
    r"|(but|though|however)[^.]{0,40}correct answer",
    re.IGNORECASE,
)
_REMARK_POSITIVE = re.compile(
    r"\b(correct|great|good|right|well done|excellent|accurate|nicely|perfect|you got it)\b",
    re.IGNORECASE,
)


def _compute_missed_ids(questions: list, answers: list, evaluation: dict) -> list:
    """Deterministic per-question correctness for the "Review Missed" set.

    MCQ / True-False: authoritative string equality on the stored answers.
    Free-text (ShortAnswer / Conceptual / etc.): derived from the LLM remark.
    A remark counts as a miss when it carries a negative marker OR spells out
    the correct answer after a qualifier ("though/but/however the correct
    answer is …"). This replaces the old substring search that mislabelled
    remarks like "Incorrect. The correct answer is X" as correct.
    """
    ans_map: dict = {}
    for a in answers:
        if isinstance(a, dict):
            qid = a.get("id") or a.get("question_id")
            if qid is not None:
                ans_map[str(qid)] = a.get("user_answer", "")

    fb_map: dict = {}
    for fb in (evaluation or {}).get("per_question_feedback", []):
        if isinstance(fb, dict):
            idx = fb.get("question_number")
            if idx is not None:
                fb_map[int(idx)] = fb.get("remark", "")

    missed_ids: list[str] = []
    for i, q in enumerate(questions, 1):
        if not isinstance(q, dict):
            continue
        qid = str(q.get("id") or q.get("question_id") or f"q-{i}")
        qtype = str(q.get("type", "")).strip().lower()
        user_ans = str(ans_map.get(qid) or q.get("user_answer", "")).strip()
        correct_ans = str(q.get("answer", "")).strip()

        is_correct = False
        if qtype in ("mcq", "true/false", "true false"):
            is_correct = user_ans != "" and user_ans.lower() == correct_ans.lower()
        else:
            remark = fb_map.get(i, "")
            if remark:
                if _REMARK_NEGATIVE.search(remark):
                    is_correct = False
                else:
                    is_correct = bool(_REMARK_POSITIVE.search(remark))

        if not is_correct:
            missed_ids.append(qid)

    return missed_ids


@router.get("/quiz/attempts/{attempt_id}/missed")
async def get_quiz_attempt_missed(
    attempt_id: str,
    lecture_id: str = "default",
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    await ensure_lecture_access(lecture_id, user, db)
    with _db(lecture_id) as conn:
        _ensure_quiz_attempts_table(conn)
        _ensure_quiz_attempts_correct_ids(conn)
        row = conn.execute(
            "SELECT questions_json, evaluation_json, answers_json, correct_ids_json FROM quiz_attempts WHERE id = ? AND lecture_id = ? AND user_id = ?",
            (attempt_id, lecture_id, str(user.id) if user else ""),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Quiz attempt not found")

        questions = json_lib.loads(row[0]) if row[0] else []
        evaluation = json_lib.loads(row[1]) if row[1] else {}
        answers = json_lib.loads(row[2]) if row[2] else []
        correct_ids = json_lib.loads(row[3]) if row[3] else []

        all_ids = []
        for i, q in enumerate(questions, 1):
            if isinstance(q, dict):
                all_ids.append(str(q.get("id") or q.get("question_id") or f"q-{i}"))

        if correct_ids:
            correct_set = {str(cid) for cid in correct_ids}
            missed_ids = [qid for qid in all_ids if qid not in correct_set]
        else:
            missed_ids = _compute_missed_ids(questions, answers, evaluation)

        return {"attempt_id": attempt_id, "question_ids": missed_ids}
