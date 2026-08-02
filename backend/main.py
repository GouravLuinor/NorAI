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
from fastapi import Form, UploadFile
import asyncio
import json as json_lib
import random
import uuid
import re
from backend.orchestrator import run_pipeline, get_or_create_task_sync
from contextlib import contextmanager
from pathlib import Path
from typing import List
from backend.dependencies import get_lecture_db_path, _get_or_create_lecture_graph, sanitize_lecture_id
import sqlite3
import time
import threading
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from backend.lecture_registry import list_lectures, get_lecture
from config import MODEL_NAME, get_api_key, CHECKPOINT_DB_PATH
from backend.dependencies import invoke_tutor
from backend.lecture_registry import get_lecture
# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="NorAI Tutor API")

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
def _db():
    """Yield a short-lived SQLite connection and commit/close on exit."""
    CHECKPOINT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(CHECKPOINT_DB_PATH), timeout=10.0)
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


def _get_all_thread_ids() -> list[str]:
    """
    BUG-7: Union of (1) user_threads and (2) LangGraph checkpoints.
    Each source is guarded independently so a missing table never crashes.
    Result is sorted ascending (threads are prefixed with 'thread-17…' so
    lexicographic ≈ chronological).
    """
    threads: set[str] = set()
    try:
        with _db() as conn:
            _ensure_user_threads_table(conn)

            # Source 1: app-owned table (always safe)
            for row in conn.execute("SELECT thread_id FROM user_threads"):
                if row[0]:
                    threads.add(row[0])

            # Source 2: LangGraph checkpoints (may not exist / different schema)
            try:
                for row in conn.execute("SELECT DISTINCT thread_id FROM checkpoints"):
                    if row[0]:
                        threads.add(row[0])
            except sqlite3.OperationalError:
                pass  # table doesn't exist yet — that's fine

    except Exception as exc:
        print(f"[threads] DB error: {exc}")

    return sorted(threads)

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

class ChatResponse(BaseModel):
    answer: str
    retrieved_chunks: list
    retrieved_images: list
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

# ---------------------------------------------------------------------------
# Chat endpoints
# ---------------------------------------------------------------------------

@app.post("/chat")
async def chat(req: ChatRequest):
    try:
        result = await asyncio.to_thread(
            invoke_tutor,
            thread_id=req.thread_id,
            user_question=req.user_question,
            lecture_title=req.lecture_title,
            lecture_id=req.lecture_id,
            message_id=req.message_id,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    async def event_generator():
        try:
            result = await asyncio.to_thread(
                invoke_tutor,
                thread_id=req.thread_id,
                user_question=req.user_question,
                lecture_title=req.lecture_title,
                lecture_id=req.lecture_id,        # ← added
                message_id=req.message_id,
            )
            answer = result.get("answer", "")
            for ch in answer:
                yield f"data: {ch}\n\n"
                await asyncio.sleep(0.015)

            final_data = {
                "assistant_message_id": result.get("assistant_message_id"),
                "retrieved_chunks": result.get("retrieved_chunks", []),
                "retrieved_images": result.get("retrieved_images", []),
                "chapter_id": result.get("chapter_id"),
                "thread_id": result.get("thread_id"),
            }
            yield f"data: {json_lib.dumps(final_data)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            yield f"data: [ERROR] {exc}\n\n"

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
        graph, _ = _get_or_create_lecture_graph(lecture_id)
        config = {"configurable": {"thread_id": thread_id}}
        snapshot = graph.get_state(config)
        if not snapshot or not snapshot.values:
            return {"thread_id": thread_id, "messages": []}

        result = []
        for msg in snapshot.values.get("messages", []):
            role = "user" if msg.__class__.__name__ == "HumanMessage" else "assistant"
            content = msg.content
            if role == "assistant":
                content = re.sub(r'\*\*Sources\*\*[\s\S]*$', '', content).strip()

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
            "last_retrieved_images": last_retrieved_images
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

def _load_quiz_questions(chapter_id: int | None) -> list[dict]:
    if chapter_id is not None:
        path = Path(f"outputs/assessment/assessment_chapter_{chapter_id}.json")
    else:
        path = Path("outputs/assessment/assessment.json")
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        data = json_lib.load(f)
    questions = data if isinstance(data, list) else []
    return [q for q in questions if isinstance(q, dict)]


@app.get("/quiz/questions")
async def quiz_questions(chapter_id: int | None = None, n: int = 5, lecture_id: str = "default"):
    info = get_lecture(lecture_id)
    base = Path(info["output_dir"]) if info else Path("outputs")
    path = base / "assessment" / f"assessment_chapter_{chapter_id}.json" if chapter_id else base / "assessment" / "assessment.json"
    if not path.exists():
        return []
    questions = json_lib.loads(path.read_text(encoding="utf-8"))
    if not isinstance(questions, list):
        questions = []
    questions = [q for q in questions if isinstance(q, dict)]
    if len(questions) > n:
        questions = random.sample(questions, n)
    return questions


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

    llm = ChatGoogleGenerativeAI(
        model=MODEL_NAME,
        temperature=0.2,
        google_api_key=get_api_key(),
    )
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
        print(f"[quiz/evaluate] Parse error: {exc}")
        return {
            "evaluation": {
                "final_score": None,
                "total_questions": len(req.questions),
                "per_question_feedback": [],
                "overall_insights": text,
            }
        }


@app.get("/flashcards")
async def flashcards(chapter_id: int | None = None, n: int | None = None, lecture_id: str = "default"):
    info = get_lecture(lecture_id)
    base = Path(info["output_dir"]) if info else Path("outputs")
    path = base / "flashcards" / f"flashcards_chapter_{chapter_id}.json" if chapter_id else base / "flashcards" / "flashcards.json"
    if not path.exists():
        return []
    cards = json_lib.loads(path.read_text(encoding="utf-8"))
    if n is not None and len(cards) > n:
        cards = random.sample(cards, n)
    return cards


@app.get("/summary")
async def chapter_summary(chapter_id: int, lecture_id: str = "default"):
    info = get_lecture(lecture_id)
    base = Path(info["output_dir"]) if info else Path("outputs")
    path = base / "revision" / f"revision_chapter_{chapter_id}.md"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Summary not found for this chapter")
    return path.read_text(encoding="utf-8")


@app.get("/notes/{chapter_id}")
async def study_notes(chapter_id: int, lecture_id: str = "default"):
    info = get_lecture(lecture_id)
    base = Path(info["output_dir"]) if info else Path("outputs")
    path = base / "notes" / f"chapter_{chapter_id}.md"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Study notes not found")
    return path.read_text(encoding="utf-8")

@app.get("/screenshots/{chapter_id}")
async def chapter_screenshots(chapter_id: int, lecture_id: str = "default"):
    info = get_lecture(lecture_id)
    base = Path(info["output_dir"]) if info else Path("outputs")
    path = base / "screenshots" / "selected" / f"chapter_{chapter_id}_screenshots.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        data = json_lib.load(f)
    return data.get("screenshots", [])

app.mount("/static", StaticFiles(directory="outputs"), name="static")



# ── Upload & Processing ──────────────────────────────────────────────────────

@app.post("/process")
async def start_processing(
    source_type: str = Form(...),
    url: str | None = Form(None),
    file: UploadFile | None = None,
):
    task_id = str(uuid.uuid4())

    file_path = None
    if file:
        upload_dir = Path("outputs/uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)
        raw_name = Path(file.filename or "upload.mp4").name
        safe_filename = re.sub(r"[^a-zA-Z0-9_.-]", "_", raw_name)
        file_path = upload_dir / f"{task_id}_{safe_filename}"
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

    # Run pipeline in a background thread — keeps the event loop free
    thread = threading.Thread(
        target=run_pipeline,
        args=(task_id, source_type, url, str(file_path) if file_path else None),
        daemon=True,
    )
    thread.start()

    return {"task_id": task_id}

@app.get("/lectures")
async def get_lectures():
    return list_lectures()


@app.get("/lectures/{lecture_id}")
async def get_lecture_info(lecture_id: str):
    try:
        clean_id = sanitize_lecture_id(lecture_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid lecture_id format")
    info = get_lecture(clean_id)
    if not info:
        raise HTTPException(status_code=404, detail="Lecture not found")
    return info


@app.get("/outline")
async def get_outline(lecture_id: str = "default"):
    """Return the lecture outline as JSON (for the sidebar chapter list)."""
    info = get_lecture(lecture_id)
    base = Path(info["output_dir"]) if info else Path("outputs")
    path = base / "notes" / "lecture_outline.json"
    if not path.exists():
        return {"chapters": []}
    with open(path, encoding="utf-8") as f:
        return json_lib.load(f)



@app.get("/process/{task_id}/status")
async def get_task_status(task_id: str):
    """Return current progress as a single JSON object."""
    tp = get_or_create_task_sync(task_id)
    return {
        "stage": "complete" if tp.finished and not tp.error else tp.stage,
        "message": tp.error or tp.message,
        "progress": tp.percent,
    }