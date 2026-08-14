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
import secrets
import uuid
import re
import os
from dotenv import load_dotenv

load_dotenv()
from backend import jobs
from contextlib import contextmanager, asynccontextmanager
from pathlib import Path
from fastapi import Depends, FastAPI, Form, HTTPException, Request, UploadFile
from typing import Any, List, Optional
import sqlite3
import time
from datetime import datetime, timezone
from backend.dependencies import get_lecture_db_path, _aget_or_create_lecture_graph, sanitize_lecture_id, configure_sqlite


from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, Response, FileResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, SystemMessage
from backend.lecture_registry import list_lectures, get_lecture
from backend.video_map import build_video_map
from backend.dependencies import ainvoke_tutor, astream_tutor_tokens
from backend.lecture_registry import get_lecture
from ingest.ingest import is_youtube_url, is_gdrive_url
from ingest.ingest import probe_video_metadata
from backend.estimator import estimate_pipeline
from backend.auth import get_current_user_optional, get_current_user
from backend.db.database import get_db
from backend.db.models import User, Subscription, Lecture, UsageLog, Course, CourseLecture, ShareLink
from backend.usage import record_pipeline_outcome
from tutor.llm import make_chat_llm
from flashcards.sm2 import apply_sm2, due_in_days
from flashcards.anki import build_package
from config import (
    CHECKPOINT_DB_PATH,
    LEMONSQUEEZY_CHECKOUT_STARTER_URL, LEMONSQUEEZY_CHECKOUT_PRO_URL,
    LEMONSQUEEZY_CUSTOMER_PORTAL_URL,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func
import logging

# P5.1: structured JSON logging (console + rotating outputs/backend.log).
from backend.logging_config import setup_logging, bind, clear_context

setup_logging()

from backend.db.migrate import run_migrations
from backend.routers import webhooks


@asynccontextmanager
async def lifespan(app: FastAPI):
    # P4.3: versioned schema (Alembic) instead of create_all. Runs in a thread
    # because the alembic command is synchronous; idempotent on every boot.
    await asyncio.to_thread(run_migrations)
    # P4.1: boot the DB-backed pipeline queue supervisor, then one GC sweep
    # for stale uploads / orphaned lecture dirs.
    jobs.start_supervisor()
    await asyncio.to_thread(jobs.gc_sweep)
    yield


app = FastAPI(title="NorAI Tutor API", lifespan=lifespan)


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


# ── SPA static serving (P5.4) ─────────────────────────────────────────────────
# When a production build of the frontend exists (frontend/dist), the backend
# serves it directly so a single container runs the whole app. Registered as a
# middleware + catch-all route so the API routes below still take precedence.

SPA_DIST_DIR = Path(os.environ.get("NORAI_SPA_DIST", "frontend/dist")).resolve()


def _spa_index() -> Optional[Path]:
    candidate = SPA_DIST_DIR / "index.html"
    return candidate if candidate.is_file() else None


# SPA client-side routes (everything Vite's history-mode router owns).
SPA_HTML_ROUTES = {"/", "/pricing", "/billing", "/usage", "/courses"}
SPA_HTML_PREFIXES = ("/app", "/workspace", "/process/", "/print", "/share/")


@app.middleware("http")
async def spa_middleware(request: Request, call_next):
    """Serve index.html for HTML navigations to client-side routes, mirroring
    the Vite dev proxy's /billing bypass. API fetches send Accept: */* (never
    text/html), so they still hit the JSON routes."""
    if request.method == "GET" and _spa_index() is not None:
        accept = request.headers.get("accept", "")
        path = request.url.path
        if "text/html" in accept and (
            path in SPA_HTML_ROUTES or path.startswith(SPA_HTML_PREFIXES)
        ):
            return FileResponse(SPA_DIST_DIR / "index.html")
    return await call_next(request)


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
    _ensure_flashcard_schedule_columns(conn)


def _ensure_flashcard_schedule_columns(conn: sqlite3.Connection) -> None:
    """Lazily add the SM-2 schedule columns (P6.2) to flashcard_ratings.

    Migration-friendly: the base table is created *without* these columns in
    older DBs, so we ALTER once and swallow the duplicate-column error — the
    same lazy-migrate pattern as `_ensure_quiz_attempts_correct_ids`.
    """
    for col, ddl in (
        ("easiness", "REAL"),
        ("reps", "INTEGER"),
        ("interval_days", "INTEGER"),
        ("due_at", "TEXT"),
        ("last_reviewed_at", "TEXT"),
    ):
        try:
            conn.execute(f"ALTER TABLE flashcard_ratings ADD COLUMN {col} {ddl}")
        except sqlite3.OperationalError:
            pass  # column already exists


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

class CourseCreateRequest(BaseModel):
    name: str
    description: str | None = None

class CourseUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None

class AddLectureRequest(BaseModel):
    lecture_id: str

class ReorderLecturesRequest(BaseModel):
    lecture_ids: list[str] = []

class ShareLinkRequest(BaseModel):
    allow_tutor_chat: bool = True

# ---------------------------------------------------------------------------
# Chat endpoints
# ---------------------------------------------------------------------------

def _flush_tutor_usage(
    user: Optional[User],
    lecture_id: str,
    before: dict,
    diff_usage_fn,
) -> None:
    """P6.5: after a chat turn, meter its tutor-stage usage into the DB.

    Filters the ledger diff to the `tutor` stage (a concurrent pipeline run on
    the same process must not be attributed to a chat turn). Anonymous users and
    unowned lectures are skipped inside record_tutor_turn.
    """
    try:
        from backend.usage import record_tutor_turn

        stages = diff_usage_fn(before)
        tutor = next((s for s in stages if s.get("stage") == "tutor"), None)
        if tutor is None:
            return
        record_tutor_turn(
            user_id=str(user.id) if user and user.id else None,
            lecture_id=lecture_id,
            stage="tutor",
            model=tutor.get("model"),
            input_tokens=int(tutor.get("input_tokens", 0) or 0),
            output_tokens=int(tutor.get("output_tokens", 0) or 0),
            calls=int(tutor.get("calls", 1) or 1),
            cost_usd=float(tutor.get("cost_usd", 0.0) or 0.0),
        )
    except Exception:
        logging.getLogger("norai").exception("Failed to meter tutor usage for lecture %s", lecture_id)


async def _flush_tutor_usage_async(
    user: Optional[User],
    lecture_id: str,
    before: dict,
    diff_usage_fn,
) -> None:
    """Async variant of _flush_tutor_usage for use inside the event loop."""
    try:
        from backend.usage import record_tutor_turn_async

        stages = diff_usage_fn(before)
        tutor = next((s for s in stages if s.get("stage") == "tutor"), None)
        if tutor is None:
            return
        await record_tutor_turn_async(
            user_id=str(user.id) if user and user.id else None,
            lecture_id=lecture_id,
            stage="tutor",
            model=tutor.get("model"),
            input_tokens=int(tutor.get("input_tokens", 0) or 0),
            output_tokens=int(tutor.get("output_tokens", 0) or 0),
            calls=int(tutor.get("calls", 1) or 1),
            cost_usd=float(tutor.get("cost_usd", 0.0) or 0.0),
        )
    except Exception:
        logging.getLogger("norai").exception("Failed to meter tutor usage for lecture %s", lecture_id)


@app.post("/chat")
async def chat(
    req: ChatRequest,
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    try:
        bind(lecture_id=req.lecture_id, thread_id=req.thread_id)
        # P6.4: chat is a tutor-gated write — owner OR share link with tutor
        # chat enabled. Anonymous users without a share link are 404'd.
        await ensure_lecture_access(req.lecture_id or "default", user, db, require_tutor=True)
        # P6.5: diff the tutor ledger across this turn so we can meter its cost.
        from backend.usage_ledger import snapshot_usage, diff_usage
        from backend.usage import record_tutor_turn

        _tutor_before = snapshot_usage()
        result = await ainvoke_tutor(
            thread_id=req.thread_id,
            user_question=req.user_question,
            lecture_title=req.lecture_title,
            lecture_id=req.lecture_id,
            message_id=req.message_id,
            study_mode=req.study_mode,
            persona_instructions=req.persona_instructions,
        )
        await _flush_tutor_usage_async(user, req.lecture_id or "default", _tutor_before, diff_usage)
        return result
    except HTTPException as e:
        # P6.4: let access-gate 404s (unshared / tutor-disabled) propagate as-is.
        raise e
    except Exception as e:
        logging.getLogger("norai").exception("POST /chat failed")
        raise HTTPException(status_code=500, detail="Internal error processing your request")




@app.post("/chat/stream")
async def chat_stream(
    req: ChatRequest,
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    bind(lecture_id=req.lecture_id, thread_id=req.thread_id)
    await ensure_lecture_access(req.lecture_id or "default", user, db, require_tutor=True)

    async def event_generator():
        try:
            # P6.5: snapshot the tutor ledger before the turn (metered after).
            from backend.usage_ledger import snapshot_usage, diff_usage
            from backend.usage import record_tutor_turn

            _tutor_before = snapshot_usage()
            # P6.1: REAL token streaming. astream_tutor_tokens drives the graph
            # with astream_events and yields the incremental tokens produced by
            # generate_answer_node, then a single {final: ...} payload with the
            # committed turn's metadata. The wire contract (data: {t} chunks,
            # data: {final}, data: [DONE]) is unchanged, so the frontend's
            # reassembly is untouched — only time-to-first-token changes.
            async for frame in astream_tutor_tokens(
                thread_id=req.thread_id,
                user_question=req.user_question,
                lecture_title=req.lecture_title,
                lecture_id=req.lecture_id,
                message_id=req.message_id,
                study_mode=req.study_mode,
                persona_instructions=req.persona_instructions,
            ):
                yield f"data: {json_lib.dumps(frame)}\n\n"
            yield "data: [DONE]\n\n"
            await _flush_tutor_usage_async(user, req.lecture_id or "default", _tutor_before, diff_usage)
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
            if conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='deleted_threads'").fetchone():
                conn.execute("DELETE FROM deleted_threads WHERE thread_id = ?", (thread_id,))
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
                conn.execute("CREATE TABLE IF NOT EXISTS deleted_threads (thread_id TEXT PRIMARY KEY)")
                conn.execute("INSERT OR REPLACE INTO deleted_threads (thread_id) VALUES (?)", (thread_id,))
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


@app.post("/quiz/explain")
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

@app.post("/quiz/attempts")
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
async def upsert_flashcard_ratings(
    req: UpsertFlashcardRatingsRequest,
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    await ensure_lecture_access(req.lecture_id, user, db, require_tutor=True)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    schedule: dict = {}
    with _db(req.lecture_id) as conn:
        _ensure_flashcard_ratings_table(conn)
        for item in req.ratings:
            prev = conn.execute(
                "SELECT easiness, reps, interval_days, due_at, last_reviewed_at "
                "FROM flashcard_ratings "
                "WHERE lecture_id=? AND chapter_id=? AND card_key=?",
                (req.lecture_id, req.chapter_id or 0, item.card_key),
            ).fetchone()
            prior = None
            if prev:
                prior = {
                    "easiness": prev[0],
                    "reps": prev[1],
                    "interval_days": prev[2],
                    "due_at": prev[3] or "",
                    "last_reviewed_at": prev[4] or "",
                }
            state = apply_sm2(item.rating, state=prior, reviewed_at=now)
            conn.execute(
                "INSERT INTO flashcard_ratings "
                "(lecture_id, chapter_id, card_key, rating, updated_at, "
                " easiness, reps, interval_days, due_at, last_reviewed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(lecture_id, chapter_id, card_key) DO UPDATE SET "
                "rating=excluded.rating, updated_at=excluded.updated_at, "
                "easiness=excluded.easiness, reps=excluded.reps, "
                "interval_days=excluded.interval_days, due_at=excluded.due_at, "
                "last_reviewed_at=excluded.last_reviewed_at",
                (req.lecture_id, req.chapter_id or 0, item.card_key, item.rating,
                 now, state["easiness"], state["reps"], state["interval_days"],
                 state["due_at"], state["last_reviewed_at"]),
            )
            schedule[item.card_key] = {
                "rating": item.rating,
                "easiness": state["easiness"],
                "reps": state["reps"],
                "interval_days": state["interval_days"],
                "due_at": state["due_at"],
                "due_in_days": due_in_days(state),
                "last_reviewed_at": state["last_reviewed_at"],
            }
    return {"success": True, "count": len(req.ratings), "schedule": schedule}


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
        where = "WHERE lecture_id=?"
        params: list = [lecture_id]
        if chapter_id is not None:
            where += " AND chapter_id=?"
            params.append(chapter_id)
        cursor = conn.execute(
            "SELECT card_key, rating, easiness, reps, interval_days, due_at, last_reviewed_at "
            f"FROM flashcard_ratings {where}",
            params,
        )
        rows = cursor.fetchall()
        ratings: dict = {}
        schedule: dict = {}
        for r in rows:
            key = r[0]
            ratings[key] = r[1]
            schedule[key] = {
                "rating": r[1],
                "easiness": r[2],
                "reps": r[3],
                "interval_days": r[4],
                "due_at": r[5],
                "due_in_days": due_in_days({"due_at": r[5]}),
                "last_reviewed_at": r[6],
            }
        return {"ratings": ratings, "schedule": schedule}


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
    # Fall back to the legacy outputs/ root (same as /outline) so the
    # "default" demo lecture — which is never registered — still resolves.
    base = Path(info["output_dir"]) if info else Path("outputs")

    title = (info.get("name") or info.get("title") or "") if info else ""
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


@app.get("/flashcards/export")
async def export_flashcards(
    lecture_id: str = "default",
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Download the lecture's flashcard deck as an Anki `.apkg` file (P6.2).

    Pure file reads + a deterministic 0-LLM transform — never regenerates
    cards. Per-chapter files take priority (they carry chapter titles), with a
    fallback to the combined `flashcards.json`.
    """
    await ensure_lecture_access(lecture_id, user, db)
    info = get_lecture(lecture_id)
    if not info:
        raise HTTPException(status_code=404, detail="Lecture not found")
    base = Path(info["output_dir"])
    title = info.get("name") or info.get("title") or "Lecture"

    cards: list[dict] = []
    deck_dir = base / "flashcards"
    chapter_files = sorted(deck_dir.glob("flashcards_chapter_*.json"))
    if chapter_files:
        for p in chapter_files:
            raw = json_lib.loads(p.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                cid = raw.get("chapter_id")
                ctitle = raw.get("chapter_title") or f"Chapter {cid}"
                chapter_cards = raw.get("flashcards", [])
            else:
                cid, ctitle, chapter_cards = None, "", raw
            for c in chapter_cards:
                cards.append({
                    "front": c.get("front", ""),
                    "back": c.get("back", ""),
                    "explanation": c.get("explanation", ""),
                    "chapter_title": ctitle,
                    "chapter_id": cid,
                })
    else:
        combined = deck_dir / "flashcards.json"
        if combined.exists():
            data = json_lib.loads(combined.read_text(encoding="utf-8"))
            for c in (data.get("flashcards", []) if isinstance(data, dict) else data):
                cards.append({
                    "front": c.get("front", ""),
                    "back": c.get("back", ""),
                    "explanation": c.get("explanation", ""),
                    "chapter_title": "",
                    "chapter_id": None,
                })

    if not cards:
        raise HTTPException(status_code=404, detail="No flashcards found for this lecture")

    safe_lecture = sanitize_lecture_id(lecture_id) or "lecture"
    payload = build_package(cards, deck_name=f"NorAI · {title}", lecture_tag=f"lecture:{safe_lecture}")
    return Response(
        content=payload,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="norai-{safe_lecture}.apkg"'},
    )


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

async def _assert_shared_or_404(
    lecture_id: str,
    db: AsyncSession,
    require_tutor: bool,
) -> None:
    """404 unless a valid (non-expired) share link grants access to lecture_id.

    `require_tutor` tightens the grant to links that also allow AI tutor chat,
    so read endpoints stay open on any share link while chat / quiz / flashcard
    writes need the owner's explicit opt-in.
    """
    now = datetime.now(timezone.utc)
    stmt = select(ShareLink).where(
        ShareLink.lecture_id == lecture_id,
        or_(
            ShareLink.expires_at.is_(None),
            ShareLink.expires_at > now,
        ),
    )
    if require_tutor:
        stmt = stmt.where(ShareLink.allow_tutor_chat.is_(True))
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Lecture not found")


NORAI_DEV_ACCESS = (
    os.environ.get("NORAI_DEV_ACCESS", "0") == "1"
    or os.environ.get("NORAI_DEV_INSECURE_AUTH", "0") == "1"
)


async def ensure_lecture_access(
    lecture_id: str,
    user: Optional[User],
    db: AsyncSession,
    require_tutor: bool = False,
) -> None:
    """Scope a lecture-scoped read/write to its owner or a valid share link.

    Closed-by-default (P6.4): a lecture is accessible only by its owner (when a
    user is authenticated) or via a valid non-expired share link. The legacy
    "default" lecture stays open. When `require_tutor` is True (chat / quiz /
    flashcard writes), a share link must also allow tutor chat.

    Dev escape hatch: when NORAI_DEV_ACCESS=1 or NORAI_DEV_INSECURE_AUTH=1,
    any lecture present in the local file registry or outputs/ directory is
    accessible without requiring authentication or share links.
    """
    if lecture_id in (None, "", "default"):
        return
    if (
        os.environ.get("NORAI_DEV_ACCESS", "0") == "1"
        or os.environ.get("NORAI_DEV_INSECURE_AUTH", "0") == "1"
    ):
        if get_lecture(lecture_id) is not None or (Path("outputs") / lecture_id).exists():
            return
    if user is None:
        # Anonymous (no token): only a valid share link grants access.
        await _assert_shared_or_404(lecture_id, db, require_tutor)
        return
    result = await db.execute(
        select(Lecture.id).where(Lecture.id == lecture_id, Lecture.user_id == user.id)
    )
    if result.scalar_one_or_none() is None:
        await _assert_shared_or_404(lecture_id, db, require_tutor)


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


@app.get("/usage")
async def get_usage(
    period: str = "month",
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """P6.5: usage/cost dashboard aggregates over the user's UsageLog rows.

    Returned period is calendar-month by default (`period=today` for the
    current day, `period=month` default). All figures are derived from the
    metered UsageLog rows; `estimated_cost_usd` for embedding stages is an
    estimate (billable chars / 4) and the API flags `is_estimated`.
    """
    if period not in ("month", "today"):
        period = "month"
    if not user:
        return {
            "is_anonymous": True,
            "totals": {"api_calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "minutes": 0},
            "by_stage": [],
            "by_day": [],
            "by_lecture": [],
            "period": period,
            "is_estimated": False,
        }

    now = datetime.now(timezone.utc)
    if period == "month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    base = select(UsageLog).where(
        UsageLog.user_id == user.id,
        UsageLog.created_at >= start,
    )

    rows: list[Any] = list((await db.execute(base.order_by(UsageLog.created_at))).scalars().all())

    input_tokens = sum(int(r.input_tokens or 0) for r in rows)
    output_tokens = sum(int(r.output_tokens or 0) for r in rows)
    calls = sum(int(r.calls or 0) for r in rows)
    cost = sum(float(r.estimated_cost_usd or 0.0) for r in rows)

    # Quota minutes consumed this month (for the summary card).
    result = await db.execute(select(Subscription).where(Subscription.user_id == user.id))
    sub = result.scalar_one_or_none()
    minutes = sub.used_minutes_this_month if sub else 0

    by_stage: dict[str, dict] = {}
    for r in rows:
        stage_name = str(r.stage)
        s = by_stage.setdefault(
            stage_name,
            {"stage": stage_name, "calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0},
        )
        s["calls"] += int(r.calls or 0)
        s["input_tokens"] += int(r.input_tokens or 0)
        s["output_tokens"] += int(r.output_tokens or 0)
        s["cost_usd"] += float(r.estimated_cost_usd or 0.0)

    by_day: dict[str, dict] = {}
    for r in rows:
        day = (r.created_at if r.created_at.tzinfo else r.created_at.replace(tzinfo=timezone.utc))
        key = str(day.strftime("%Y-%m-%d"))
        d = by_day.setdefault(
            key, {"date": key, "calls": 0, "cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0}
        )
        d["calls"] += int(r.calls or 0)
        d["cost_usd"] += float(r.estimated_cost_usd or 0.0)
        d["input_tokens"] += int(r.input_tokens or 0)
        d["output_tokens"] += int(r.output_tokens or 0)

    by_lecture: dict[str, dict] = {}
    for r in rows:
        lk = str(r.lecture_id)
        lec = by_lecture.setdefault(
            lk, {"lecture_id": lk, "calls": 0, "cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0}
        )
        lec["calls"] += int(r.calls or 0)
        lec["cost_usd"] += float(r.estimated_cost_usd or 0.0)
        lec["input_tokens"] += int(r.input_tokens or 0)
        lec["output_tokens"] += int(r.output_tokens or 0)

    # Sort by cost desc so the frontend can render top contributors.
    by_stage_list = sorted(by_stage.values(), key=lambda x: x["cost_usd"], reverse=True)
    by_day_list = sorted(by_day.values(), key=lambda x: x["date"])
    by_lecture_list = sorted(by_lecture.values(), key=lambda x: x["cost_usd"], reverse=True)

    return {
        "user_id": str(user.id) if user else None,
        "is_anonymous": user.is_anonymous if user else True,
        "period": period,
        "is_estimated": any(r.stage == "embed" for r in rows),
        "totals": {
            "api_calls": calls,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": round(cost, 6),
            "minutes": minutes,
        },
        "by_stage": by_stage_list,
        "by_day": by_day_list,
        "by_lecture": by_lecture_list,
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
    course_id: str | None = Form(None),
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
    if source_type == "youtube" and url:
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

    # P6.4: file the new lecture into the caller's course when one is given.
    if course_id:
        cresult = await db.execute(
            select(Course).where(Course.id == course_id, Course.user_id == user.id)
        )
        if cresult.scalar_one_or_none() is not None:
            max_pos = await db.execute(
                select(func.coalesce(func.max(CourseLecture.position), 0)).where(
                    CourseLecture.course_id == course_id
                )
            )
            db.add(
                CourseLecture(
                    course_id=course_id,
                    lecture_id=task_id,
                    position=max_pos.scalar_one() + 1,
                )
            )
            await db.commit()

    return {"task_id": task_id}

@app.get("/lectures")
async def get_lectures(
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """List lectures.

    Authenticated: the caller's own lectures (DB is the ownership source of
    truth, enriched with the file registry's chapter counts / titles).
    Anonymous: the legacy open registry (dev / default lecture).
    """
    if user is None:
        return list_lectures()

    result = await db.execute(
        select(Lecture)
        .where(Lecture.user_id == user.id)
        .order_by(Lecture.created_at.desc())
    )
    rows = result.scalars().all()
    registry = {lec.get("lecture_id"): lec for lec in list_lectures()}
    out = []
    for row in rows:
        meta = registry.get(row.id, {})
        out.append({
            "lecture_id": row.id,
            "title": meta.get("title") or row.title,
            "status": row.status,
            "source_type": row.source_type,
            "duration_seconds": row.duration_seconds,
            "chapter_count": meta.get("chapter_count", 0),
            "created_at": meta.get("created_at") or (
                row.created_at.isoformat() if row.created_at else None
            ),
            "output_dir": meta.get("output_dir"),
        })
    return out



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
    # P6.3: merge DB source fields so the frontend knows whether a YouTube
    # embed is possible (the registry itself only stores id/title/output_dir).
    row = (
        await db.execute(select(Lecture).where(Lecture.id == clean_id))
    ).scalar_one_or_none()
    info["source_type"] = row.source_type if row else None
    info["source_url"] = row.source_url if row else None
    info["status"] = row.status if row else None
    info["duration_seconds"] = row.duration_seconds if row else None
    return info


# ---------------------------------------------------------------------------
# P6.4 — Course collections (owner-scoped)
# ---------------------------------------------------------------------------

def _app_origin() -> str:
    """Browser origin used to build share URLs (dev default = Vite server)."""
    return os.environ.get("NORAI_APP_URL", "http://localhost:5173").rstrip("/")


def _new_share_slug() -> str:
    return secrets.token_urlsafe(12)


async def _get_owned_course(course_id: str, user: User, db: AsyncSession) -> Course:
    result = await db.execute(
        select(Course).where(Course.id == course_id, Course.user_id == user.id)
    )
    course = result.scalar_one_or_none()
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


def _registry_map() -> dict:
    return {lec.get("lecture_id"): lec for lec in list_lectures()}


def _lecture_listing(row: Lecture, meta: dict) -> dict:
    return {
        "lecture_id": row.id,
        "title": meta.get("title") or row.title,
        "status": row.status,
        "source_type": row.source_type,
        "duration_seconds": row.duration_seconds,
        "chapter_count": meta.get("chapter_count", 0),
        "created_at": meta.get("created_at") or (
            row.created_at.isoformat() if row.created_at else None
        ),
    }


@app.get("/courses")
async def list_courses(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Course).where(Course.user_id == user.id).order_by(Course.created_at.desc())
    )
    courses = result.scalars().all()
    out = []
    for c in courses:
        count = await db.execute(
            select(func.count())
            .select_from(CourseLecture)
            .where(CourseLecture.course_id == c.id)
        )
        out.append({
            "course_id": c.id,
            "name": c.name,
            "description": c.description,
            "lecture_count": count.scalar_one(),
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })
    return {"courses": out}


@app.post("/courses")
async def create_course(
    req: CourseCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Course name is required")
    course = Course(user_id=user.id, name=name[:256], description=req.description)
    db.add(course)
    await db.commit()
    return {
        "course_id": course.id,
        "name": course.name,
        "description": course.description,
        "lecture_count": 0,
    }


@app.get("/courses/{course_id}")
async def get_course(
    course_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    course = await _get_owned_course(course_id, user, db)
    links = (
        await db.execute(
            select(CourseLecture)
            .where(CourseLecture.course_id == course_id)
            .order_by(CourseLecture.position)
        )
    ).scalars().all()
    registry = _registry_map()
    lectures = []
    for link in links:
        row = (
            await db.execute(select(Lecture).where(Lecture.id == link.lecture_id))
        ).scalar_one_or_none()
        if row is None:
            continue
        lectures.append(_lecture_listing(row, registry.get(row.id, {})))
    return {
        "course_id": course.id,
        "name": course.name,
        "description": course.description,
        "lectures": lectures,
    }


@app.patch("/courses/{course_id}")
async def update_course(
    course_id: str,
    req: CourseUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    course = await _get_owned_course(course_id, user, db)
    if req.name is not None:
        name = req.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Course name cannot be empty")
        course.name = name[:256]
    if req.description is not None:
        course.description = req.description
    await db.commit()
    return {
        "course_id": course.id,
        "name": course.name,
        "description": course.description,
    }


@app.delete("/courses/{course_id}")
async def delete_course(
    course_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    course = await _get_owned_course(course_id, user, db)
    await db.delete(course)
    await db.commit()
    return {"success": True}


@app.post("/courses/{course_id}/lectures")
async def add_lecture_to_course(
    course_id: str,
    req: AddLectureRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_owned_course(course_id, user, db)
    result = await db.execute(
        select(Lecture).where(Lecture.id == req.lecture_id, Lecture.user_id == user.id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Lecture not found")

    existing = await db.execute(
        select(CourseLecture).where(
            CourseLecture.course_id == course_id,
            CourseLecture.lecture_id == req.lecture_id,
        )
    )
    if existing.scalar_one_or_none() is None:
        max_pos = await db.execute(
            select(func.coalesce(func.max(CourseLecture.position), 0)).where(
                CourseLecture.course_id == course_id
            )
        )
        db.add(
            CourseLecture(
                course_id=course_id,
                lecture_id=req.lecture_id,
                position=max_pos.scalar_one() + 1,
            )
        )
        await db.commit()
    return {"success": True, "course_id": course_id, "lecture_id": req.lecture_id}


@app.delete("/courses/{course_id}/lectures/{lecture_id}")
async def remove_lecture_from_course(
    course_id: str,
    lecture_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_owned_course(course_id, user, db)
    result = await db.execute(
        select(CourseLecture).where(
            CourseLecture.course_id == course_id,
            CourseLecture.lecture_id == lecture_id,
        )
    )
    link = result.scalar_one_or_none()
    if link is not None:
        await db.delete(link)
        await db.commit()
    return {"success": True}


@app.put("/courses/{course_id}/lectures")
async def reorder_course_lectures(
    course_id: str,
    req: ReorderLecturesRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_owned_course(course_id, user, db)
    for position, lecture_id in enumerate(req.lecture_ids):
        result = await db.execute(
            select(CourseLecture).where(
                CourseLecture.course_id == course_id,
                CourseLecture.lecture_id == lecture_id,
            )
        )
        link = result.scalar_one_or_none()
        if link is None:
            raise HTTPException(
                status_code=400, detail=f"Lecture {lecture_id} is not in this course"
            )
        link.position = position
    await db.commit()
    return {"success": True}


# ---------------------------------------------------------------------------
# P6.4 — Share links (owner creates/revokes; viewers read via the slug)
# ---------------------------------------------------------------------------

@app.post("/lectures/{lecture_id}/share")
async def create_share_link(
    lecture_id: str,
    req: ShareLinkRequest | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    clean_id = sanitize_lecture_id(lecture_id)
    result = await db.execute(
        select(Lecture).where(Lecture.id == clean_id, Lecture.user_id == user.id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Lecture not found")

    allow_tutor_chat = req.allow_tutor_chat if req is not None else True
    existing = await db.execute(
        select(ShareLink).where(
            ShareLink.lecture_id == clean_id,
            ShareLink.created_by == user.id,
        )
    )
    link = existing.scalar_one_or_none()
    if link is None:
        link = ShareLink(
            id=_new_share_slug(),
            lecture_id=clean_id,
            created_by=user.id,
            allow_tutor_chat=allow_tutor_chat,
        )
        db.add(link)
    else:
        # Re-sharing refreshes the existing slug (re-enabling an expired link).
        link.allow_tutor_chat = allow_tutor_chat
        link.expires_at = None
    await db.commit()
    return {
        "slug": link.id,
        "url": f"{_app_origin()}/share/{link.id}",
        "allow_tutor_chat": link.allow_tutor_chat,
    }


@app.get("/lectures/{lecture_id}/share")
async def get_share_link(
    lecture_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the owner's existing share link for a lecture, or 404 if none.

    Lets the ShareModal show the live link on open instead of resolving a
    random slug by lecture id (which always 404'd).
    """
    clean_id = sanitize_lecture_id(lecture_id)
    result = await db.execute(
        select(ShareLink).where(
            ShareLink.lecture_id == clean_id,
            ShareLink.created_by == user.id,
        )
    )
    link = result.scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=404, detail="No share link exists for this lecture")
    return {
        "slug": link.id,
        "url": f"{_app_origin()}/share/{link.id}",
        "allow_tutor_chat": link.allow_tutor_chat,
    }


@app.patch("/lectures/{lecture_id}/share")
async def update_share_link(
    lecture_id: str,
    req: ShareLinkRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    clean_id = sanitize_lecture_id(lecture_id)
    result = await db.execute(
        select(ShareLink).where(
            ShareLink.lecture_id == clean_id,
            ShareLink.created_by == user.id,
        )
    )
    link = result.scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=404, detail="No share link exists for this lecture")
    link.allow_tutor_chat = req.allow_tutor_chat
    await db.commit()
    return {
        "slug": link.id,
        "url": f"{_app_origin()}/share/{link.id}",
        "allow_tutor_chat": link.allow_tutor_chat,
    }


@app.delete("/lectures/{lecture_id}/share")
async def delete_share_link(
    lecture_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    clean_id = sanitize_lecture_id(lecture_id)
    result = await db.execute(
        select(ShareLink).where(
            ShareLink.lecture_id == clean_id,
            ShareLink.created_by == user.id,
        )
    )
    link = result.scalar_one_or_none()
    if link is not None:
        await db.delete(link)
        await db.commit()
    return {"success": True}


@app.get("/share/{slug}")
async def resolve_share_link(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Resolve an unlisted share slug to a lecture the viewer may open.

    Public (no auth required): anyone holding the link may read the lecture's
    artifacts. Returns only navigation metadata — never source URLs.
    """
    result = await db.execute(select(ShareLink).where(ShareLink.id == slug))
    link = result.scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=404, detail="Share link not found")
    now = datetime.now(timezone.utc)
    if link.expires_at is not None:
        expires_at = link.expires_at
        if expires_at.tzinfo is None:  # SQLite stores naive UTC datetimes
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < now:
            raise HTTPException(status_code=404, detail="Share link has expired")
    lecture = (
        await db.execute(select(Lecture).where(Lecture.id == link.lecture_id))
    ).scalar_one_or_none()
    if lecture is None:
        raise HTTPException(status_code=404, detail="Lecture not found")
    return {
        "lecture_id": lecture.id,
        "title": lecture.title,
        "status": lecture.status,
        "source_type": lecture.source_type,
        "allow_tutor_chat": link.allow_tutor_chat,
    }


@app.get("/video-map")
async def get_video_map(
    lecture_id: str = "default",
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """P6.3: per-lecture seek map (chapter + chunk timestamps) for click-to-video."""
    await ensure_lecture_access(lecture_id, user, db)
    info = get_lecture(lecture_id)
    base = Path(info["output_dir"]) if info else Path("outputs")
    return build_video_map(base)


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
                    if int(cid) == chapter_id:
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

# ── SPA fallback (P5.4) ───────────────────────────────────────────────────────
# Serve built frontend assets under /assets etc. when a production build is
# present; everything else is handled by the API routes + spa_middleware.

@app.get("/{path:path}", include_in_schema=False)
async def spa_assets(path: str):
    if _spa_index() is not None:
        candidate = (SPA_DIST_DIR / path).resolve()
        try:
            candidate.relative_to(SPA_DIST_DIR)
        except ValueError:
            raise HTTPException(status_code=404, detail="Not found")
        if candidate.is_file():
            return FileResponse(candidate)
    raise HTTPException(status_code=404, detail="Not found")
