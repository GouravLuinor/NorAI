"""
backend/main.py

FastAPI application for the NorAI tutor.
"""
import asyncio
import json as json_lib
import random
import sqlite3
import time
from pathlib import Path
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from tutor.config import MODEL_NAME, get_api_key, CHECKPOINT_DB_PATH
from backend.dependencies import invoke_tutor, _graph

app = FastAPI(title="NorAI Tutor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", 
        "http://127.0.0.1:5173",  # <-- Added this line
        "http://localhost:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _get_all_thread_ids() -> list[str]:
    """Return all distinct thread_ids across user_threads and checkpoints databases safely."""
    try:
        # Guarantee directory exists so sqlite3 doesn't crash
        CHECKPOINT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(CHECKPOINT_DB_PATH))
        conn.execute("CREATE TABLE IF NOT EXISTS user_threads (thread_id TEXT PRIMARY KEY)")
        
        threads = set()
        
        # 1. Always get explicitly created threads
        cursor = conn.execute("SELECT thread_id FROM user_threads")
        for row in cursor.fetchall():
            if row[0]:
                threads.add(row[0])
                
        # 2. Safely try to get LangGraph checkpoints (this table might not exist yet)
        try:
            cursor = conn.execute("SELECT thread_id FROM checkpoints")
            for row in cursor.fetchall():
                if row[0]:
                    threads.add(row[0])
        except sqlite3.OperationalError:
            pass
            
        conn.close()
        
        # Sort chronologically (since they start with 'thread-17...')
        sorted_threads = sorted(list(threads))
        return sorted_threads
    except Exception as e:
        print(f"Error fetching threads: {e}")
        return []
    
# ── Request / Response models ─────────────────────────────────────────────────

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


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    try:
        result = invoke_tutor(
            thread_id=req.thread_id,
            user_question=req.user_question,
            lecture_title=req.lecture_title,
        )
        return ChatResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
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

        except Exception as e:
            yield f"data: [ERROR] {str(e)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

@app.post("/threads")
async def create_thread_endpoint():
    thread_id = f"thread-{int(time.time() * 1000)}"
    try:
        CHECKPOINT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(CHECKPOINT_DB_PATH))
        conn.execute("CREATE TABLE IF NOT EXISTS user_threads (thread_id TEXT PRIMARY KEY)")
        conn.execute("INSERT INTO user_threads (thread_id) VALUES (?)", (thread_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        pass
    return {"thread_id": thread_id}

@app.get("/threads")
async def list_threads():
    return {"threads": _get_all_thread_ids()}

@app.get("/threads/{thread_id}")
async def get_thread(thread_id: str):
    try:
        config = {"configurable": {"thread_id": thread_id}}
        snapshot = _graph.get_state(config)
        if not snapshot.values:
            return {"thread_id": thread_id, "messages": []}
            
        messages = snapshot.values.get("messages", [])
        result = []
        for msg in messages:
            result.append({
                "role": "user" if msg.__class__.__name__ == "HumanMessage" else "assistant",
                "content": msg.content,
            })
        return {"thread_id": thread_id, "messages": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/threads/{thread_id}")
async def delete_thread(thread_id: str):
    try:
        conn = sqlite3.connect(str(CHECKPOINT_DB_PATH))
        
        tables_to_clean = ["checkpoints", "checkpoint_blobs", "checkpoint_writes", "user_threads"]
        for table in tables_to_clean:
            try:
                conn.execute(f"DELETE FROM {table} WHERE thread_id = ?", (thread_id,))
            except sqlite3.OperationalError:
                pass
                
        conn.commit()
        conn.close()
        return {"deleted": thread_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── Quiz, Summary, and Flashcards ─────────────────────────────────────────────

def _load_quiz_questions(chapter_id: int | None) -> list[dict]:
    questions = []
    if chapter_id is not None:
        path = Path(f"outputs/assessment/assessment_chapter_{chapter_id}.json")
        if path.exists():
            with open(path, encoding="utf-8") as f:
                data = json_lib.load(f)
                questions = data if isinstance(data, list) else []
    else:
        combined = Path("outputs/assessment/assessment.json")
        if combined.exists():
            with open(combined, encoding="utf-8") as f:
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
        "Important: final_score must be the number of correct answers (e.g., 4), NOT a percentage (e.g., 80).",
        "",
        "Do NOT include any other text.",
        "",
    ]

    if req.elapsed_seconds:
        mins = req.elapsed_seconds // 60
        secs = req.elapsed_seconds % 60
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
        text = " ".join(block["text"] for block in text if isinstance(block, dict) and "text" in block)

    try:
        json_start = text.find('{')
        json_end = text.rfind('}') + 1
        if json_start != -1 and json_end > json_start:
            json_str = text[json_start:json_end]
            data = json_lib.loads(json_str)
            evaluation = QuizEvaluation(**data)
            return {
                "evaluation": {
                    "final_score": evaluation.final_score,
                    "total_questions": evaluation.total_questions,
                    "per_question_feedback": [fb.dict() for fb in evaluation.per_question_feedback],
                    "overall_insights": evaluation.overall_insights,
                }
            }
        else:
            raise ValueError("No JSON found")
    except Exception as e:
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
    if chapter_id is not None:
        path = Path(f"outputs/flashcards/flashcards_chapter_{chapter_id}.json")
    else:
        path = Path("outputs/flashcards/flashcards.json")
    
    if not path.exists():
        return []
    
    cards = json_lib.loads(path.read_text(encoding="utf-8"))
    if n is not None and len(cards) > n:
        cards = random.sample(cards, n)
    
    return cards

@app.get("/summary")
async def chapter_summary(chapter_id: int):
    if chapter_id is None:
        raise HTTPException(status_code=400, detail="chapter_id is required")
    path = Path(f"outputs/revision/revision_chapter_{chapter_id}.md")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Summary not found for this chapter")
    return path.read_text(encoding="utf-8")