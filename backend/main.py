import asyncio
from fastapi.responses import StreamingResponse
import random
import json as json_lib
from pathlib import Path
import re
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from tutor.config import MODEL_NAME, TEMPERATURE, get_api_key
from pydantic import BaseModel
from typing import List, Optional
import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage


"""
backend/main.py

FastAPI application for the NorAI tutor.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.dependencies import invoke_tutor

app = FastAPI(title="NorAI Tutor API")

# Allow requests from the Vite dev server during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite default
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response models ─────────────────────────────────────────────────

class ChatRequest(BaseModel):
    thread_id: str
    user_question: str
    lecture_title: str = ""   # only needed for the very first message


class ChatResponse(BaseModel):
    answer: str
    retrieved_chunks: list
    retrieved_images: list
    chapter_id: int | None
    thread_id: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    Synchronous chat endpoint.  Returns the full answer, retrieved
    chunks, and retrieved images in one go.
    """
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
    """
    Streaming chat endpoint.  Returns the answer as Server-Sent Events
    (SSE), one character at a time, so the frontend can display it as
    it arrives.
    """
    async def event_generator():
        try:
            result = invoke_tutor(
                thread_id=req.thread_id,
                user_question=req.user_question,
                lecture_title=req.lecture_title,
            )
            answer = result.get("answer", "")

            # Stream the answer character by character
            for ch in answer:
                yield f"data: {ch}\n\n"
                await asyncio.sleep(0.015)   # ~15 ms between chars

            # Send the final result (chunks, images) as a JSON event
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

# ── Quiz ──────────────────────────────────────────────────────────────────────

def _load_quiz_questions(chapter_id: int | None) -> list[dict]:
    """Load questions for a chapter, or all chapters if chapter_id is None."""
    if chapter_id is not None:
        path = Path(f"outputs/assessment/assessment_chapter_{chapter_id}.json")
        if path.exists():
            with open(path) as f:
                return json_lib.load(f)
    # Fallback to combined file
    combined = Path("outputs/assessment/assessment.json")
    if combined.exists():
        with open(combined) as f:
            all_qs = json_lib.load(f)
        if chapter_id is not None:
            return [q for q in all_qs if q.get("chapter_id") == chapter_id]
        return all_qs
    return []


@app.get("/quiz/questions")
async def quiz_questions(chapter_id: int | None = None, n: int = 5):
    """Return up to `n` random quiz questions for the given chapter."""
    questions = _load_quiz_questions(chapter_id)
    if len(questions) > n:
        questions = random.sample(questions, n)
    return questions


class QuizEvaluateRequest(BaseModel):
    questions: list[dict]   # each must have: question, answer, user_answer (and optionally type, options, explanation)
    # user_answer is the string the user typed / selected


class QuizEvaluateRequest(BaseModel):
    questions: list[dict]
    elapsed_seconds: int = 0
    confidences: list[str] = []


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


@app.post("/quiz/evaluate")
async def quiz_evaluate(req: QuizEvaluateRequest):
    """Send the answered questions to the LLM for structured evaluation."""
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

    # Parse the JSON output
    try:
        # Extract JSON from response (in case it wraps it in markdown code block)
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
        # Fallback: return raw text if parsing fails
        return {
            "evaluation": {
                "final_score": None,
                "total_questions": len(req.questions),
                "per_question_feedback": [],
                "overall_insights": text,
            }
        }