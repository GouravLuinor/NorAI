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
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from tutor.config import MODEL_NAME, get_api_key, CHECKPOINT_DB_PATH
from backend.dependencies import invoke_tutor, _graph

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
    conn = sqlite3.connect(str(CHECKPOINT_DB_PATH))
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

class ChatRequest(BaseModel):
    thread_id: str
    user_question: str
    lecture_title: str = ""

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

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    try:
        result = invoke_tutor(
            thread_id=req.thread_id,
            user_question=req.user_question,
            lecture_title=req.lecture_title,
        )
        return ChatResponse(**result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    async def event_generator():
        try:
            result = invoke_tutor(
                thread_id=req.thread_id,
                user_question=req.user_question,
                lecture_title=req.lecture_title,
            )
            answer = result.get("answer", "")
            for ch in answer:
                yield f"data: {ch}\n\n"
                await asyncio.sleep(0.015)

            final_data = {
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

@app.post("/threads")
async def create_thread_endpoint(id: Optional[str] = None):
    """
    BUG-7: Write ONLY to user_threads — never touch the checkpoints table.
    LangGraph manages checkpoints with its own schema; injecting rows directly
    can corrupt its internal state or fail silently on schema mismatches.
    """
    thread_id = id if id else f"thread-{int(time.time() * 1000)}"
    try:
        with _db() as conn:
            _ensure_user_threads_table(conn)
            conn.execute(
                "INSERT OR IGNORE INTO user_threads (thread_id) VALUES (?)",
                (thread_id,),
            )
    except Exception as exc:
        # Log but don't crash — the frontend has already updated optimistically
        print(f"[create_thread] DB error: {exc}")
    return {"thread_id": thread_id}


@app.get("/threads")
async def list_threads():
    return {"threads": _get_all_thread_ids()}


@app.get("/threads/{thread_id}")
async def get_thread(thread_id: str):
    """
    BUG-4: Return an empty message list for brand-new threads (not 404).
    A thread exists as soon as the frontend creates it; LangGraph only writes
    a checkpoint after the first message, so snapshot.values can legitimately
    be empty without being an error.
    """
    try:
        config = {"configurable": {"thread_id": thread_id}}
        snapshot = _graph.get_state(config)

        # Empty snapshot = valid new thread, not an error
        if not snapshot or not snapshot.values:
            return {"thread_id": thread_id, "messages": []}

        result = []
        for msg in snapshot.values.get("messages", []):
            result.append({
                "role": "user" if msg.__class__.__name__ == "HumanMessage" else "assistant",
                "content": msg.content,
            })
        return {"thread_id": thread_id, "messages": result}

    except Exception as exc:
        # LangGraph may throw if it can't find the thread at all — treat as empty
        print(f"[get_thread] {thread_id}: {exc}")
        return {"thread_id": thread_id, "messages": []}


@app.delete("/threads/{thread_id}")
async def delete_thread(thread_id: str):
    try:
        with _db() as conn:
            for table in ["checkpoints", "checkpoint_blobs", "checkpoint_writes", "user_threads"]:
                try:
                    conn.execute(f"DELETE FROM {table} WHERE thread_id = ?", (thread_id,))
                except sqlite3.OperationalError:
                    pass  # table doesn't exist yet
        return {"deleted": thread_id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

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
async def quiz_questions(chapter_id: int | None = None, n: int = 5):
    questions = _load_quiz_questions(chapter_id)
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
async def flashcards(chapter_id: int | None = None, n: int | None = None):
    path = (
        Path(f"outputs/flashcards/flashcards_chapter_{chapter_id}.json")
        if chapter_id is not None
        else Path("outputs/flashcards/flashcards.json")
    )
    if not path.exists():
        return []
    cards = json_lib.loads(path.read_text(encoding="utf-8"))
    if n is not None and len(cards) > n:
        cards = random.sample(cards, n)
    return cards


@app.get("/summary")
async def chapter_summary(chapter_id: int):
    path = Path(f"outputs/revision/revision_chapter_{chapter_id}.md")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Summary not found for this chapter")
    return path.read_text(encoding="utf-8")


@app.get("/notes/{chapter_id}")
async def study_notes(chapter_id: int):
    """Return the study notes Markdown for a chapter."""
    path = Path(f"outputs/notes/chapter_{chapter_id}.md")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Study notes not found for this chapter")
    return path.read_text(encoding="utf-8")

@app.get("/screenshots/{chapter_id}")
async def chapter_screenshots(chapter_id: int):
    """Return the list of selected screenshots for a chapter."""
    path = Path(f"outputs/screenshots/selected/chapter_{chapter_id}_screenshots.json")
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        data = json_lib.load(f)
    return data.get("screenshots", [])

app.mount("/static", StaticFiles(directory="outputs"), name="static")


@app.get("/download/{doc_type}")
async def download_pdf(doc_type: str):
    """Return the pre‑generated PDF for the given document type."""
    allowed = {"study_notes", "revision", "assessment"}
    if doc_type not in allowed:
        raise HTTPException(status_code=400, detail="Invalid document type")

    pdf_path = f"outputs/{doc_type}.pdf"
    if not Path(pdf_path).exists():
        raise HTTPException(status_code=404, detail="PDF not found. Run python backend/generate_pdfs.py first.")
    return FileResponse(pdf_path, media_type="application/pdf", filename=f"{doc_type}.pdf")