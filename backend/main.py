"""
backend/main.py

Fix log:
  BUG-2  CORS origins widened to cover all common Vite dev ports.
  BUG-7  /threads POST now writes ONLY to user_threads (safe, app-owned table).
         It never touches the checkpoints table — LangGraph manages that schema
         and can use an incompatible column layout.
         GET /threads unions user_threads + checkpoints safely with try/except
         per table so a missing table never crashes the whole endpoint.
  BUG-4  GET /threads/{thread_id} now returns an empty message list (not 404)
         when the thread exists in user_threads but has no LangGraph checkpoint
         yet (brand new thread that hasn't received a message).
"""
import asyncio
import json as json_lib
import random
import uuid
import re
import os
from backend import jobs
from contextlib import contextmanager
from pathlib import Path
from fastapi import Depends, FastAPI, Form, HTTPException, Request, UploadFile
from typing import List, Optional
import sqlite3
import time
from datetime import datetime, timezone
from backend.dependencies import get_lecture_db_path, _aget_or_create_lecture_graph, sanitize_lecture_id, configure_sqlite


from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, SystemMessage
from backend.lecture_registry import list_lectures, get_lecture
from backend.dependencies import ainvoke_tutor
from backend.lecture_registry import get_lecture
from ingest.ingest import is_youtube_url, is_gdrive_url
from ingest.ingest import probe_video_metadata
from backend.estimator import estimate_pipeline
from backend.auth import get_current_user_optional, get_current_user
from backend.db.database import get_db
from backend.db.models import User, Subscription, Lecture
from backend.usage import record_pipeline_outcome
from tutor.llm import make_chat_llm
from config import (
    CHECKPOINT_DB_PATH,
    LEMONSQUEEZY_CHECKOUT_STARTER_URL, LEMONSQUEEZY_CHECKOUT_PRO_URL,
    LEMONSQUEEZY_CUSTOMER_PORTAL_URL,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

# P5.1: structured JSON logging (console + rotating outputs/backend.log).
from backend.logging_config import setup_logging, bind, clear_context

setup_logging()

app = FastAPI(title="NorAI Tutor API")

from backend.db.migrate import run_migrations
from backend.routers import webhooks


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """P5.1: tag every request with a request_id (accept/echo X-Request-ID)."""
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
    bind(request_id=request_id)
    try:
        response = await call_next(request)
    except Exception:
        clear_context()
        raise
    response.headers["X-Request-ID"] = request_id
    clear_context()
    return response


@app.on_event("startup")
async def on_startup():
    # P4.3: versioned schema (Alembic) instead of create_all. Runs in a thread
    # because the alembic command is synchronous; idempotent on every boot.
    await asyncio.to_thread(run_migrations)
    # P4.1: boot the DB-backed pipeline queue supervisor, then one GC sweep
    # for stale uploads / orphaned lecture dirs.
    jobs.start_supervisor()
    await asyncio.to_thread(jobs.gc_sweep)

app.include_router(webhooks.router)

# Log the full detail of any unhandled exception server-side, but never leak
# raw exception text to clients.
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logging.getLogger("norai").exception(
        "Unhandled exception on %s %s", request.method, request.url.path
    )
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# BUG-2: include every port Vite or the preview server might use
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:4173",   # vite preview
        "http://127.0.0.1:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

@contextmanager
def _db(lecture_id: str = "default"):
    """Yield a short-lived SQLite connection and commit/close on exit.

    Lecture-scoped: quiz/flashcard persistence lands in the same DB as that
    lecture's tutor checkpoints (outputs/{lecture_id}/tutor/). The global
    'default' lecture keeps using the root CHECKPOINT_DB_PATH for backward
    compatibility with the default tutor graph.
    """
    db_path = CHECKPOINT_DB_PATH if (not lecture_id or lecture_id == "default") else get_lecture_db_path(lecture_id)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=10.0)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
    except Exception:
        pass
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _ensure_user_threads_table(conn: sqlite3.Connection) -> None:
    """Create the app-owned user_threads table if it doesn't exist."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS user_threads "
        "(thread_id TEXT PRIMARY KEY, created_at INTEGER DEFAULT (strftime('%s','now')))"
    )


def _ensure_quiz_attempts_table(conn: sqlite3.Connection) -> None:
    """Create the quiz_attempts table if it doesn't exist."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS quiz_attempts ("
        "id TEXT PRIMARY KEY, "
        "lecture_id TEXT, "
        "chapter_id INTEGER, "
        "difficulty TEXT, "
        "started_at TEXT, "
        "finished_at TEXT, "
        "questions_json TEXT, "
        "answers_json TEXT, "
        "confidences_json TEXT, "
        "evaluation_json TEXT, "
        "score REAL, "
        "total INTEGER"
        ")"
    )


def _ensure_quiz_attempts_correct_ids(conn: sqlite3.Connection) -> None:
    """Add the correct_ids_json column to quiz_attempts if it's missing.

    Migration-friendly: older DBs created before this column existed won't
    get it from CREATE TABLE IF NOT EXISTS, so we ALTER lazily and swallow
    the duplicate-column error.
    """
    try:
        conn.execute("ALTER TABLE quiz_attempts ADD COLUMN correct_ids_json TEXT")
    except sqlite3.OperationalError:
        pass  # column already exists


def _ensure_flashcard_ratings_table(conn: sqlite3.Connection) -> None:
    """Create the flashcard_ratings table if it doesn't exist."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS flashcard_ratings ("
        "lecture_id TEXT, "
        "chapter_id INTEGER, "
        "card_key TEXT, "
        "rating TEXT, "
        "updated_at TEXT, "
        "PRIMARY KEY (lecture_id, chapter_id, card_key)"
        ")"
    )


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class CreateThreadRequest(BaseModel):
    thread_id: str | None = None

class ChatRequest(BaseModel):
    thread_id: str
    user_question: str
    lecture_title: str = ""
    lecture_id: str | None = None   # ← new field
    message_id: str | None = None
    study_mode: str = "default"
    persona_instructions: str = ""

class ChatResponse(BaseModel):
    answer: str
    retrieved_chunks: list
    retrieved_images: list
    verified_citations: list = []   # P3.3
    chapter_id: int | None
    thread_id: str

class QuestionFeedback(BaseModel):
    question_number: int
    remark: str

class QuizEvaluation(BaseModel):
    final_score: int
    total_questions: int
    per_question_feedback: List[QuestionFeedback]
    overall_insights: str

class QuizEvaluateRequest(BaseModel):
    questions: list[dict]
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
    questions: list[dict] = []

class FinishQuizAttemptRequest(BaseModel):
    answers: list[dict] = []
    confidences: list[str] = []
    evaluation: dict | None = None
    score: float = 0.0
    total: int = 0
    correct_ids: list[str] = []

class FlashcardRatingItem(BaseModel):
    card_key: str
    rating: str

class UpsertFlashcardRatingsRequest(BaseModel):
    lecture_id: str = "default"
    chapter_id: int | None = None
    ratings: list[FlashcardRatingItem] = []

# ---------------------------------------------------------------------------
# Chat endpoints
# ---------------------------------------------------------------------------

@app.post("/chat")
async def chat(req: ChatRequest):
    try:
        bind(lecture_id=req.lecture_id, thread_id=req.thread_id)
        result = await ainvoke_tutor(
            thread_id=req.thread_id,
            user_question=req.user_question,
            lecture_title=req.lecture_title,
            lecture_id=req.lecture_id,
            message_id=req.message_id,
            study_mode=req.study_mode,
            persona_instructions=req.persona_instructions,
        )
        return result
    except Exception as e:
        logging.getLogger("norai").exception("POST /chat failed")
        raise HTTPException(status_code=500, detail="Internal error processing your request")




@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    bind(lecture_id=req.lecture_id, thread_id=req.thread_id)

    async def event_generator():
        try:
            result = await ainvoke_tutor(
                thread_id=req.thread_id,
                user_question=req.user_question,
                lecture_title=req.lecture_title,
                lecture_id=req.lecture_id,        # ← added
                message_id=req.message_id,
                study_mode=req.study_mode,
                persona_instructions=req.persona_instructions,
            )
            answer = result.get("answer", "")

            # Stream the already-computed answer in small chunks instead of
            # per-character (old 15ms/char throttle regressed latency on long
            # answers). Chunks are JSON-wrapped so embedded newlines survive the
            # SSE line framing; the frontend reassembles them exactly.
            STEP = 24
            i = 0
            n = len(answer)
            while i < n:
                end = min(i + STEP, n)
                if end < n:
                    nxt = answer.find(" ", end)
                    if nxt != -1 and nxt - end < 12:
                        end = nxt + 1
                yield f"data: {json_lib.dumps({'t': answer[i:end]})}\n\n"
                await asyncio.sleep(0.002)
                i = end

            final_data = {
                "assistant_message_id": result.get("assistant_message_id"),
                "retrieved_chunks": result.get("retrieved_chunks", []),
                "retrieved_images": result.get("retrieved_images", []),
                "verified_citations": result.get("verified_citations", []),
                "chapter_id": result.get("chapter_id"),
                "thread_id": result.get("thread_id"),
            }
            yield f"data: {json_lib.dumps({'final': final_data})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            logging.getLogger("norai").exception("POST /chat/stream failed")
            yield "data: [ERROR] An internal error occurred while streaming the answer.\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

# ---------------------------------------------------------------------------
# Thread endpoints
# ---------------------------------------------------------------------------

@app.get("/threads")
async def list_threads(lecture_id: str = "default"):
    """Return all thread IDs for a lecture."""
    db_path = get_lecture_db_path(lecture_id)
    if not db_path.exists():
        return {"threads": []}

    threads = set()
    try:
        conn = sqlite3.connect(str(db_path), timeout=10.0)
        configure_sqlite(conn)
        try:
            # 1) Auto-migrate old threads: check if a checkpoint has HumanMessage
            try:
                conn.execute("CREATE TABLE IF NOT EXISTS user_threads (thread_id TEXT PRIMARY KEY)")
                cursor = conn.execute("SELECT thread_id, checkpoint FROM checkpoints")
                rows = cursor.fetchall()
                for row in rows:
                    tid = row[0]
                    chk = row[1]
                    if isinstance(chk, bytes) and b"HumanMessage" in chk:
                        conn.execute("INSERT OR IGNORE INTO user_threads (thread_id) VALUES (?)", (tid,))
                conn.commit()
            except Exception:
                pass

            # 2) user_threads table (explicitly created or migrated user threads)
            try:
                for row in conn.execute("SELECT thread_id FROM user_threads"):
                    if row[0]:
                        threads.add(row[0])
            except Exception:
                pass
        finally:
            conn.close()
    except Exception:
        pass

    return {"threads": sorted(threads)}


@app.post("/threads")
async def create_thread_endpoint(request: Request, lecture_id: str = "default"):
    """Create a new conversation thread in a lecture."""
    thread_id = None
    try:
        body = await request.json()
        thread_id = body.get("thread_id")
    except Exception:
        pass
    if not thread_id:
        thread_id = f"thread-{int(time.time() * 1000)}"
    db_path = get_lecture_db_path(lecture_id)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        conn = sqlite3.connect(str(db_path), timeout=10.0)
        configure_sqlite(conn)
        try:
            conn.execute("CREATE TABLE IF NOT EXISTS user_threads (thread_id TEXT PRIMARY KEY)")
            conn.execute("INSERT OR IGNORE INTO user_threads (thread_id) VALUES (?)", (thread_id,))
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass
    return {"thread_id": thread_id}


@app.get("/threads/{thread_id}")
async def get_thread(thread_id: str, lecture_id: str = "default"):
    """Return the full message history for a thread in a specific lecture."""
    try:
        graph, _ = await _aget_or_create_lecture_graph(lecture_id)
        config = {"configurable": {"thread_id": thread_id}}
        snapshot = await graph.aget_state(config)
        if not snapshot or not snapshot.values:
            return {"thread_id": thread_id, "messages": []}

        result = []
        for msg in snapshot.values.get("messages", []):
            class_name = msg.__class__.__name__
            # SystemMessages are internal (system prompt, context blocks, memory
            # summaries) — never render them as conversation turns.
            if class_name == "SystemMessage":
                continue
            role = "user" if class_name == "HumanMessage" else "assistant"
            content = msg.content
            if role == "assistant":
                content = re.sub(r'(\*\*Sources\*\*|\n\nSources\b|Sources\s*[\:\•]|Sources\b[\s\S]*$)[\s\S]*$', '', content, flags=re.IGNORECASE).strip()

            result.append({
                "id": msg.id,
                "role": role,
                "content": content,
            })

        last_retrieved_chunks = snapshot.values.get("retrieved_chunks", [])
        last_retrieved_images = snapshot.values.get("retrieved_images", [])

        return {
            "thread_id": thread_id,
            "messages": result,
            "last_retrieved_chunks": last_retrieved_chunks,
            "last_retrieved_images": last_retrieved_images,
            "verified_citations": snapshot.values.get("verified_citations", []),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/threads/{thread_id}")
async def delete_thread(thread_id: str, lecture_id: str = "default"):
    """Delete a thread from a lecture."""
    db_path = get_lecture_db_path(lecture_id)
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path), timeout=10.0)
            configure_sqlite(conn)
            try:
                for table in ["checkpoints", "checkpoint_blobs", "checkpoint_writes", "user_threads"]:
                    try:
                        conn.execute(f"DELETE FROM {table} WHERE thread_id = ?", (thread_id,))
                    except sqlite3.OperationalError:
                        pass
                conn.commit()
            finally:
                conn.close()
        except Exception:
            pass
    return {"deleted": thread_id}

# ---------------------------------------------------------------------------
# Quiz, Summary, Flashcards
# ---------------------------------------------------------------------------

@app.get("/quiz/questions")
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


@app.post("/quiz/evaluate")
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
        prompt_lines.append(f"Q{i} ({q.get('type', '')}): {q['question']}")
        if q.get("options"):
            prompt_lines.append(f"Options: {', '.join(q['options'])}")
        prompt_lines.append(f"Your answer: {q.get('user_answer', '')}")
        prompt_lines.append(f"Correct answer: {q['answer']}")
        if q.get("explanation"):
            prompt_lines.append(f"Explanation: {q['explanation']}")
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
                "per_question_feedback": [fb.dict() for fb in evaluation.per_question_feedback],
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


@app.post("/quiz/explain")
async def quiz_explain(req: QuizExplainRequest):
    """Cite a question's source from the lecture index — on demand only.

    Runs a single embedding retrieval (top-1 note chunk + top-1 screenshot).
    Never regenerates. Returns source:null gracefully when the index is missing.
    """
    if not req.question.strip():
        return {"source": None, "message": "Empty question."}

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
        "text": top.get("text", "")[:400],
        "screenshot": screenshot,
    }


# ---------------------------------------------------------------------------
# Quiz Attempts & Flashcard Persistence Endpoints
# ---------------------------------------------------------------------------

@app.post("/quiz/attempts")
async def create_quiz_attempt(req: CreateQuizAttemptRequest):
    attempt_id = f"attempt-{uuid.uuid4().hex[:12]}"
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with _db(req.lecture_id) as conn:
        _ensure_quiz_attempts_table(conn)
        conn.execute(
            "INSERT INTO quiz_attempts "
            "(id, lecture_id, chapter_id, difficulty, started_at, finished_at, questions_json, answers_json, confidences_json, evaluation_json, score, total) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                attempt_id,
                req.lecture_id,
                req.chapter_id,
                req.difficulty,
                now,
                "",
                json_lib.dumps(req.questions),
                json_lib.dumps([]),
                json_lib.dumps([]),
                json_lib.dumps({}),
                0.0,
                len(req.questions),
            ),
        )
    return {"attempt_id": attempt_id}


@app.post("/quiz/attempts/{attempt_id}/finish")
async def finish_quiz_attempt(attempt_id: str, req: FinishQuizAttemptRequest, lecture_id: str = "default"):
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with _db(lecture_id) as conn:
        _ensure_quiz_attempts_table(conn)
        _ensure_quiz_attempts_correct_ids(conn)
        cursor = conn.execute(
            "UPDATE quiz_attempts SET finished_at=?, answers_json=?, confidences_json=?, evaluation_json=?, correct_ids_json=?, score=?, total=? "
            "WHERE id=? AND lecture_id=?",
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
            ),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Quiz attempt not found")
    return {"success": True, "attempt_id": attempt_id}


@app.get("/quiz/attempts")
async def list_quiz_attempts(
    lecture_id: str = "default",
    chapter_id: int | None = None,
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    await ensure_lecture_access(lecture_id, user, db)
    with _db(lecture_id) as conn:
        _ensure_quiz_attempts_table(conn)
        if chapter_id is not None:
            cursor = conn.execute(
                "SELECT id, lecture_id, chapter_id, difficulty, started_at, finished_at, score, total "
                "FROM quiz_attempts WHERE lecture_id=? AND chapter_id=? ORDER BY started_at DESC",
                (lecture_id, chapter_id),
            )
        else:
            cursor = conn.execute(
                "SELECT id, lecture_id, chapter_id, difficulty, started_at, finished_at, score, total "
                "FROM quiz_attempts WHERE lecture_id=? ORDER BY started_at DESC",
                (lecture_id,),
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


@app.get("/quiz/attempts/{attempt_id}/missed")
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
            "SELECT questions_json, evaluation_json, answers_json, correct_ids_json FROM quiz_attempts WHERE id = ? AND lecture_id = ?",
            (attempt_id, lecture_id),
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


@app.post("/flashcards/ratings")
async def upsert_flashcard_ratings(req: UpsertFlashcardRatingsRequest):
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with _db(req.lecture_id) as conn:
        _ensure_flashcard_ratings_table(conn)
        for item in req.ratings:
            conn.execute(
                "INSERT INTO flashcard_ratings (lecture_id, chapter_id, card_key, rating, updated_at) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(lecture_id, chapter_id, card_key) DO UPDATE SET rating=excluded.rating, updated_at=excluded.updated_at",
                (req.lecture_id, req.chapter_id or 0, item.card_key, item.rating, now),
            )
    return {"success": True, "count": len(req.ratings)}


@app.get("/flashcards/ratings")
async def get_flashcard_ratings(
    lecture_id: str = "default",
    chapter_id: int | None = None,
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    await ensure_lecture_access(lecture_id, user, db)
    with _db(lecture_id) as conn:
        _ensure_flashcard_ratings_table(conn)
        if chapter_id is not None:
            cursor = conn.execute(
                "SELECT card_key, rating FROM flashcard_ratings WHERE lecture_id=? AND chapter_id=?",
                (lecture_id, chapter_id),
            )
        else:
            cursor = conn.execute(
                "SELECT card_key, rating FROM flashcard_ratings WHERE lecture_id=?",
                (lecture_id,),
            )
        rows = cursor.fetchall()
        ratings = {r[0]: r[1] for r in rows}
        return {"ratings": ratings}


@app.get("/study-guide")
async def study_guide(
    lecture_id: str = "default",
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Catalog the already-generated per-chapter revision notes into one doc.

    Pure file reads — no LLM call. Returns {"title", "chapters": [{chapter_id,
    title, markdown}]} in chapter order.
    """
    await ensure_lecture_access(lecture_id, user, db)
    info = get_lecture(lecture_id)
    if not info:
        raise HTTPException(status_code=404, detail="Lecture not found")
    base = Path(info["output_dir"])

    title = info.get("name") or info.get("title") or ""
    chapters: list[dict] = []

    outline_path = base / "notes" / "lecture_outline.json"
    chapter_ids: list[int] = []
    if outline_path.exists():
        try:
            outline = json_lib.loads(outline_path.read_text(encoding="utf-8"))
            for ch in outline.get("chapters", []):
                cid = ch.get("chapter_id") or ch.get("id")
                if cid is not None:
                    chapter_ids.append(int(cid))
        except Exception:
            pass
    if not chapter_ids:
        revision_dir = base / "revision"
        if revision_dir.exists():
            chapter_ids = sorted(
                int(p.stem.replace("revision_chapter_", ""))
                for p in revision_dir.glob("revision_chapter_*.md")
                if p.stem.replace("revision_chapter_", "").isdigit()
            )

    for cid in chapter_ids:
        path = base / "revision" / f"revision_chapter_{cid}.md"
        if not path.exists():
            continue
        chapters.append({
            "chapter_id": cid,
            "title": f"Chapter {cid}",
            "markdown": path.read_text(encoding="utf-8"),
        })

    if not chapters:
        raise HTTPException(status_code=404, detail="No revision notes found for this lecture")

    return {"title": title, "chapters": chapters}


@app.get("/flashcards")
async def flashcards(
    chapter_id: int | None = None,
    n: int | None = None,
    lecture_id: str = "default",
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    await ensure_lecture_access(lecture_id, user, db)
    info = get_lecture(lecture_id)
    base = Path(info["output_dir"]) if info else Path("outputs")
    path = base / "flashcards" / f"flashcards_chapter_{chapter_id}.json" if chapter_id else base / "flashcards" / "flashcards.json"
    if not path.exists():
        return []
    raw_data = json_lib.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw_data, dict):
        cards = raw_data.get("flashcards", [])
    elif isinstance(raw_data, list):
        cards = raw_data
    else:
        cards = []
    if n is not None and len(cards) > n:
        cards = random.sample(cards, n)
    return cards


@app.get("/summary")
async def chapter_summary(
    chapter_id: int,
    lecture_id: str = "default",
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    await ensure_lecture_access(lecture_id, user, db)
    info = get_lecture(lecture_id)
    base = Path(info["output_dir"]) if info else Path("outputs")
    path = base / "revision" / f"revision_chapter_{chapter_id}.md"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Summary not found for this chapter")
    return path.read_text(encoding="utf-8")


@app.get("/notes/{chapter_id}")
async def study_notes(
    chapter_id: int,
    lecture_id: str = "default",
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    await ensure_lecture_access(lecture_id, user, db)
    info = get_lecture(lecture_id)
    base = Path(info["output_dir"]) if info else Path("outputs")
    json_path = base / "notes" / f"chapter_{chapter_id}.json"
    if json_path.exists():
        with open(json_path, encoding="utf-8") as f:
            return json_lib.load(f)
    md_path = base / "notes" / f"chapter_{chapter_id}.md"
    if not md_path.exists():
        raise HTTPException(status_code=404, detail="Study notes not found")
    return md_path.read_text(encoding="utf-8")

@app.get("/screenshots/{chapter_id}")
async def chapter_screenshots(
    chapter_id: int,
    lecture_id: str = "default",
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    await ensure_lecture_access(lecture_id, user, db)
    info = get_lecture(lecture_id)
    base = Path(info["output_dir"]) if info else Path("outputs")
    path = base / "screenshots" / "selected" / f"chapter_{chapter_id}_screenshots.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        data = json_lib.load(f)
    return data.get("screenshots", [])

# Only image assets may be served under /static. Everything else that lives in
# outputs/ (transcripts, assessment answer keys, checkpoints.sqlite, Chroma
# DBs, backend.log) is never exposed over HTTP.
STATIC_ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"}


def resolve_static_path(rest: str, base_dir: Optional[Path] = None) -> Path:
    """Resolve a /static/... path against the outputs dir with a strict allowlist."""
    base = (base_dir or Path("outputs")).resolve()
    target = (base / rest).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")
    if target.suffix.lower() not in STATIC_ALLOWED_EXTENSIONS or not target.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return target


@app.get("/static/{rest:path}")
async def static_artifact(rest: str):
    return FileResponse(resolve_static_path(rest))



# ── Upload & Processing ──────────────────────────────────────────────────────

async def ensure_lecture_access(
    lecture_id: str,
    user: Optional[User],
    db: AsyncSession,
) -> None:
    """Scope a lecture-scoped read to its owner when a user is authenticated.

    Anonymous guests keep the current open behavior (free-trial access). The
    legacy "default" lecture remains open to everyone. Because the frontend
    does not yet send the Bearer token on read endpoints, this check is
    dormant today — it engages only once a token is presented.
    """
    if user is None or lecture_id in (None, "", "default"):
        return
    result = await db.execute(
        select(Lecture.id).where(Lecture.id == lecture_id, Lecture.user_id == user.id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Lecture not found")


@app.get("/quota")
async def get_user_quota(
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Return user's active plan tier and remaining monthly lecture minutes."""
    if not user:
        # Default anonymous trial quota
        return {
            "plan_tier": "free",
            "subscription_status": "trial",
            "monthly_minutes_quota": 15,
            "used_minutes_this_month": 0,
            "remaining_minutes": 15,
            "is_anonymous": True,
        }

    # Fetch user subscription
    result = await db.execute(select(Subscription).where(Subscription.user_id == user.id))
    sub = result.scalar_one_or_none()
    
    quota = sub.monthly_minutes_quota if sub else 15
    used = sub.used_minutes_this_month if sub else 0
    remaining = max(0, quota - used)
    plan_tier = sub.plan_tier if sub else "free"
    sub_status = sub.status if sub else "trial"

    return {
        "user_id": user.id,
        "email": user.email,
        "plan_tier": plan_tier,
        "subscription_status": sub_status,
        "monthly_minutes_quota": quota,
        "used_minutes_this_month": used,
        "remaining_minutes": remaining,
        "is_anonymous": user.is_anonymous,
    }


ALLOWED_SOURCE_TYPES = {"youtube", "gdrive", "upload"}


@app.get("/billing")
async def get_billing(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the user's plan, usage, and Lemon Squeezy checkout/manage links.

    Checkout / portal URLs come from env (config.py) — they are null until the
    Lemon Squeezy store exists. `manage_url` is only offered to users who have
    an active Lemon Squeezy subscription id.
    """
    result = await db.execute(select(Subscription).where(Subscription.user_id == user.id))
    sub = result.scalar_one_or_none()

    plan_tier = sub.plan_tier if sub else "free"
    sub_status = sub.status if sub else "trial"
    quota = sub.monthly_minutes_quota if sub else 15
    used = sub.used_minutes_this_month if sub else 0
    remaining = max(0, quota - used)
    ls_sub_id = (sub.lemon_squeezy_subscription_id if sub else None) or None

    checkout_urls = {
        "starter": LEMONSQUEEZY_CHECKOUT_STARTER_URL or None,
        "pro": LEMONSQUEEZY_CHECKOUT_PRO_URL or None,
    }
    manage_url = LEMONSQUEEZY_CUSTOMER_PORTAL_URL or None

    return {
        "user_id": user.id,
        "email": user.email,
        "is_anonymous": user.is_anonymous,
        "plan_tier": plan_tier,
        "subscription_status": sub_status,
        "monthly_minutes_quota": quota,
        "used_minutes_this_month": used,
        "remaining_minutes": remaining,
        "lemon_squeezy_subscription_id": ls_sub_id,
        "checkout_urls": checkout_urls,
        "manage_url": manage_url,
    }


ALLOWED_UPLOAD_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".webm"}
MAX_UPLOAD_BYTES = int(os.environ.get("NORAI_MAX_UPLOAD_BYTES", str(2 * 1024**3)))  # default 2 GB
UPLOAD_CHUNK_BYTES = 1024 * 1024  # 1 MB

@app.post("/estimate")
async def estimate_cost(
    source_type: str = Form(...),
    url: str | None = Form(None),
    duration: float | None = Form(None),
    file: UploadFile | None = None,
):
    """Pre-flight estimate of Gemini calls + wall-clock time (P1.8).

    Probes the source duration cheaply (yt-dlp metadata-only for YouTube,
    ~2s; browser-reported duration for uploads), then returns the estimated
    call/time counts plus whether the lecture fits the free trial. Fails
    soft: when the duration can't be probed, returns {"available": false}
    and the frontend simply hides the estimate.
    """
    if source_type not in ALLOWED_SOURCE_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported source_type {source_type!r}")
    if source_type == "youtube":
        if not url or not is_youtube_url(url):
            raise HTTPException(status_code=400, detail="Invalid YouTube URL")
        probed = probe_video_metadata(url)
        if not probed:
            return {"available": False, "reason": "Could not probe duration"}
        duration_min = probed["duration_sec"] / 60.0
        est = estimate_pipeline(duration_min, source_type="youtube")
        est.update({"available": True, "title": probed.get("title")})
        return est
    if source_type == "gdrive":
        if not url or not is_gdrive_url(url):
            raise HTTPException(status_code=400, detail="Invalid Google Drive URL")
        # Drive durations can't be probed without downloading — no estimate.
        return {"available": False, "reason": "Google Drive durations are not probeable"}
    if source_type == "upload":
        if not file and duration is None:
            return {"available": False, "reason": "No file or duration provided"}
        if duration is None or duration <= 0:
            return {"available": False, "reason": "Could not read video duration"}
        est = estimate_pipeline(duration, source_type="upload")
        est.update({"available": True})
        return est
    raise HTTPException(status_code=400, detail="Unsupported source_type")


@app.post("/process")
async def start_processing(
    source_type: str = Form(...),
    url: str | None = Form(None),
    file: UploadFile | None = None,
    duration: float | None = Form(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # ── Input validation (before any resource is consumed) ─────────────────
    if source_type not in ALLOWED_SOURCE_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported source_type {source_type!r}")
    if source_type == "upload":
        if not file:
            raise HTTPException(status_code=400, detail="source_type 'upload' requires a file")
    else:
        if not url:
            raise HTTPException(status_code=400, detail=f"source_type {source_type!r} requires a url")
        if source_type == "youtube" and not is_youtube_url(url):
            raise HTTPException(status_code=400, detail="Invalid YouTube URL")
        if source_type == "gdrive" and not is_gdrive_url(url):
            raise HTTPException(status_code=400, detail="Invalid Google Drive URL")

    # ── Pre-download quota + free-trial enforcement (P2.2) ─────────────────
    # Check FIRST, then consume resources. The orchestrator's post-download
    # duration gate stays as a defense-in-depth backstop.
    result = await db.execute(select(Subscription).where(Subscription.user_id == user.id))
    sub = result.scalar_one_or_none()
    quota = sub.monthly_minutes_quota if sub else 15
    used = sub.used_minutes_this_month if sub else 0
    if used >= quota:
        raise HTTPException(
            status_code=429,
            detail=f"Monthly quota of {quota} lecture minutes reached. Please upgrade to Starter or Pro to continue processing.",
        )

    probed_sec = None
    if source_type == "youtube":
        probed = probe_video_metadata(url)
        if probed:
            probed_sec = probed["duration_sec"]
    elif source_type == "upload" and duration and duration > 0:
        probed_sec = duration * 60.0

    if probed_sec:
        import math as _math
        needed = _math.ceil(probed_sec / 60.0)
        free_limit_min = int(os.environ.get("MAX_FREE_DURATION_MIN", "15"))
        if probed_sec > free_limit_min * 60:
            raise HTTPException(
                status_code=429,
                detail=f"Lecture duration ({probed_sec / 60:.1f} mins) exceeds the free-trial limit "
                       f"of {free_limit_min} minutes. Please upgrade to Starter or Pro.",
            )
        if used + needed > quota:
            raise HTTPException(
                status_code=429,
                detail=f"This lecture needs ~{needed} of your {quota} monthly minutes "
                       f"({used} already used). Please upgrade to continue.",
            )

    task_id = str(uuid.uuid4())

    file_path = None
    if file:
        raw_name = Path(file.filename or "upload.mp4").name
        ext = Path(raw_name).suffix.lower()
        if ext not in ALLOWED_UPLOAD_EXTENSIONS:
            raise HTTPException(
                status_code=415,
                detail=f"Unsupported file type {ext!r}. Allowed: {', '.join(sorted(ALLOWED_UPLOAD_EXTENSIONS))}",
            )

        upload_dir = Path("outputs/uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)
        safe_filename = re.sub(r"[^a-zA-Z0-9_.-]", "_", raw_name)
        file_path = upload_dir / f"{task_id}_{safe_filename}"

        # Stream-write in chunks (no full-file RAM buffer), enforcing a hard cap
        # even when Content-Length is absent.
        written = 0
        with open(file_path, "wb") as f:
            while True:
                chunk = await file.read(UPLOAD_CHUNK_BYTES)
                if not chunk:
                    break
                written += len(chunk)
                if written > MAX_UPLOAD_BYTES:
                    f.close()
                    file_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"Upload exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit",
                    )
                f.write(chunk)

    # Record lecture in database (auth is now required). Status 'queued': the
    # P4.1 supervisor claims it, runs the pipeline in the worker pool, and owns
    # upload cleanup + progress/status persistence.
    lecture_record = Lecture(
        id=task_id,
        user_id=user.id,
        title="New Lecture",
        source_type=source_type,
        source_url=url or (str(file_path) if file_path else None),
        duration_seconds=int(probed_sec or 0),
        status="queued",
        queued_at=datetime.now(timezone.utc),
    )
    db.add(lecture_record)
    await db.commit()

    return {"task_id": task_id}

@app.get("/lectures")
async def get_lectures():
    return list_lectures()



@app.get("/lectures/{lecture_id}")
async def get_lecture_info(
    lecture_id: str,
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    try:
        clean_id = sanitize_lecture_id(lecture_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid lecture_id format")
    await ensure_lecture_access(clean_id, user, db)
    info = get_lecture(clean_id)
    if not info:
        raise HTTPException(status_code=404, detail="Lecture not found")
    return info


@app.get("/outline")
async def get_outline(
    lecture_id: str = "default",
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Return the lecture outline as JSON (for the sidebar chapter list)."""
    await ensure_lecture_access(lecture_id, user, db)
    info = get_lecture(lecture_id)
    base = Path(info["output_dir"]) if info else Path("outputs")
    path = base / "notes" / "lecture_outline.json"
    if not path.exists():
        return {"chapters": []}
    with open(path, encoding="utf-8") as f:
        return json_lib.load(f)


@app.get("/concept-map")
async def get_concept_map(
    chapter_id: int = 1,
    lecture_id: str = "default",
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Derive zero-LLM visual concept graph for a chapter from existing output JSONs."""
    await ensure_lecture_access(lecture_id, user, db)
    info = get_lecture(lecture_id)
    if info and "output_dir" in info and Path(info["output_dir"]).exists():
        base = Path(info["output_dir"])
    elif lecture_id and lecture_id != "default" and (Path("outputs") / lecture_id).exists():
        base = Path("outputs") / lecture_id
    else:
        base = Path("outputs")

    outline_path = base / "notes" / "lecture_outline.json"

    lecture_title = "Lecture Mind Map"
    chapter_title = f"Chapter {chapter_id}"
    focus_concepts = []
    summary = ""

    if outline_path.exists():
        try:
            with open(outline_path, encoding="utf-8") as f:
                outline = json_lib.load(f)
                lecture_title = outline.get("lecture_title", lecture_title)
                for ch in outline.get("chapters", []):
                    cid = ch.get("chapter_id") or ch.get("id")
                    if int(cid) == int(chapter_id):
                        chapter_title = ch.get("title", chapter_title)
                        focus_concepts = ch.get("focus_concepts", [])
                        summary = ch.get("summary", "")
                        break
        except Exception:
            pass

    notes_json_paths = [
        base / "notes" / f"chapter_{chapter_id}.json",
        base / "notes" / f"notes_chapter_{chapter_id}.json",
    ]

    sections_raw = []
    important_info = []
    for np in notes_json_paths:
        if np.exists():
            try:
                with open(np, encoding="utf-8") as f:
                    notes_data = json_lib.load(f)
                    sections_raw = notes_data.get("sections", [])
                    important_info = notes_data.get("important_information", []) + notes_data.get("inferred_knowledge", [])
                break
            except Exception:
                pass

    root_id = f"ch-{chapter_id}"
    nodes = []
    edges = []

    nodes.append({
        "id": root_id,
        "label": chapter_title,
        "type": "root",
        "category": "Chapter",
        "description": summary or f"Core concept structure for {chapter_title}",
    })

    if not focus_concepts and sections_raw:
        focus_concepts = [re.sub(r"^\d+[\.\s\-]+", "", s.get("title", "")).strip() for s in sections_raw if s.get("title")]

    if not focus_concepts:
        focus_concepts = [f"Section {i+1}" for i in range(len(sections_raw))] or ["Core Concepts"]

    seen_labels = set()

    used_sections = set()

    for i, fc in enumerate(focus_concepts):
        node_id = f"fc-{chapter_id}-{i}"
        fc_lower = fc.lower()
        node_desc = ""
        matched_section = None

        best_sec = None
        best_score = 0

        for sec_idx, sec in enumerate(sections_raw):
            stitle = sec.get("title", "").lower()
            content = sec.get("content_markdown", "").lower()
            score = 0
            
            if re.search(r'\b' + re.escape(fc_lower) + r'\b', stitle):
                score = 10
            elif fc_lower in stitle:
                score = 7
            elif re.search(r'\b' + re.escape(fc_lower) + r'\b', content):
                score = 5
            elif fc_lower in content:
                score = 3

            if sec_idx in used_sections:
                score = score // 3

            if score > best_score:
                best_score = score
                best_sec = (sec_idx, sec)

        if best_sec:
            sec_idx, sec = best_sec
            used_sections.add(sec_idx)
            matched_section = sec
            content = sec.get("content_markdown", "")
            clean_text = re.sub(r"[\*`#|_]|<[^>]+>", "", content).strip()
            sentences = [s.strip() for s in clean_text.split(".") if len(s.strip()) > 15]
            if sentences:
                node_desc = ". ".join(sentences[:2]) + "."
                if len(node_desc) > 220:
                    node_desc = node_desc[:217] + "..."

        if not node_desc and i < len(sections_raw) and i not in used_sections:
            used_sections.add(i)
            sec = sections_raw[i]
            content = sec.get("content_markdown", "")
            clean_text = re.sub(r"[\*`#|_]|<[^>]+>", "", content).strip()
            sentences = [s.strip() for s in clean_text.split(".") if len(s.strip()) > 15]
            if sentences:
                node_desc = ". ".join(sentences[:2]) + "."
                if len(node_desc) > 220:
                    node_desc = node_desc[:217] + "..."

        if not node_desc:
            node_desc = f"{fc} — Key architectural concept covered in {chapter_title}."

        nodes.append({
            "id": node_id,
            "label": fc,
            "type": "focus_concept",
            "category": "Core Concept",
            "description": node_desc,
        })
        edges.append({
            "id": f"edge-root-{node_id}",
            "source": root_id,
            "target": node_id,
            "label": "",
        })

        sub_items = []
        if matched_section and matched_section.get("content_markdown"):
            lines = matched_section["content_markdown"].split("\n")
            for line in lines:
                # Filter out table delimiters (| :--- | :--- |), code blocks (```), and non-text artifacts
                if re.search(r'[:\-]{2,}', line) or (line.strip().startswith('|') and ':' in line):
                    continue
                if line.strip().startswith('```') or line.strip().startswith('import ') or line.strip().startswith('export '):
                    continue

                clean_line = re.sub(r"^[\|\-\*\s\d\.]+", "", line).strip()
                clean_line = re.sub(r"[\*`#|_]|<[^>]+>", "", clean_line).strip()

                if not re.search(r'[a-zA-Z]{4,}', clean_line):
                    continue

                if clean_line and len(clean_line) > 10 and clean_line not in seen_labels:
                    sub_items.append(clean_line)
                    seen_labels.add(clean_line)
                    if len(sub_items) >= 2:
                        break

        if not sub_items and important_info:
            for item in important_info:
                clean_item = re.sub(r"^[\|\-\*\s\d\.]+", "", str(item)).strip()
                clean_item = re.sub(r"[\*`#|_]|<[^>]+>", "", clean_item).strip()
                if re.search(r'[a-zA-Z]{4,}', clean_item) and clean_item not in seen_labels:
                    sub_items.append(clean_item)
                    seen_labels.add(clean_item)
                    if len(sub_items) >= 2:
                        break

        for j, item_text in enumerate(sub_items):
            detail_id = f"dc-{chapter_id}-{i}-{j}"
            first_sentence = item_text.split(".")[0].strip()
            short_label = first_sentence[:45] + "..." if len(first_sentence) > 45 else first_sentence

            nodes.append({
                "id": detail_id,
                "label": short_label,
                "type": "detail",
                "category": "Mechanism",
                "description": item_text,
            })
            edges.append({
                "id": f"edge-{node_id}-{detail_id}",
                "source": node_id,
                "target": detail_id,
                "label": "details",
            })

    return {
        "lecture_title": lecture_title,
        "chapter_id": chapter_id,
        "root": {"id": root_id, "label": chapter_title, "summary": summary},
        "nodes": nodes,
        "edges": edges,
    }



@app.get("/process/{task_id}/status")
async def get_task_status(task_id: str):
    """Return current progress as a single JSON object (P4.1 DB-backed)."""
    status = await jobs.get_job_status(task_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Task not found")
    # Map the DB lifecycle onto the legacy {stage, message, progress} contract
    # that ProcessingPage.tsx polls on ('complete'/'error' are terminal).
    if status["status"] == "completed":
        return {"stage": "complete", "message": "All done!", "progress": 100}
    if status["status"] in ("failed", "cancelled"):
        return {
            "stage": "error",
            "message": status["error_message"] or "Pipeline failed.",
            "progress": status["progress"] or 0,
        }
    return {
        "stage": status["stage"],
        "message": status["message"],
        "progress": status["progress"] or 0,
    }


@app.post("/process/{task_id}/cancel")
async def cancel_processing_task(task_id: str):
    """Request cancellation of a queued/running pipeline (P4.1)."""
    cancelled = await jobs.request_cancel(task_id)
    if not cancelled:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"cancelled": True}