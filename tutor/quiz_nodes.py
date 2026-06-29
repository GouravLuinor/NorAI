"""
quiz_nodes.py — Quiz state machine nodes for the Phase 5 quiz tool.

Quiz flow:
    quiz_prepare → quiz_ask → [user answers] → quiz_evaluate
       ↑                                        │
       └────────────────────────────────────────┘ (more questions)
                                    │
                                    ▼
                               quiz_end → save_memory → END
"""

from __future__ import annotations

import json
import logging
import random
from pathlib import Path
from glob import glob

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

logger = logging.getLogger(__name__)

QUIZ_QUESTIONS_PER_QUIZ = 5
ASSESSMENT_GLOB = "outputs/assessment/assessment_chapter_*.json"
COMBINED_ASSESSMENT = "outputs/assessment/assessment.json"


def _load_questions(chapter_id: int | None) -> list[dict]:
    """Load questions for a specific chapter or all chapters."""
    if chapter_id is not None:
        path = Path(f"outputs/assessment/assessment_chapter_{chapter_id}.json")
        if path.exists():
            with open(path) as f:
                return json.load(f)
        else:
            logger.warning(f"No assessment file for chapter {chapter_id}, falling back to combined")
    # Load combined file
    combined = Path(COMBINED_ASSESSMENT)
    if combined.exists():
        with open(combined) as f:
            all_qs = json.load(f)
        if chapter_id is not None:
            return [q for q in all_qs if q.get("chapter_id") == chapter_id]
        return all_qs
    return []


def _format_question(q: dict, index: int, total: int) -> str:
    """Format a question for display."""
    lines = [f"**Q{index+1}/{total}** ({q.get('type', '')}): {q['question']}"]
    options = q.get("options", [])
    if options:
        letters = [chr(ord('A') + i) for i in range(len(options))]
        for letter, opt in zip(letters, options):
            lines.append(f"  {letter}) {opt}")
    return "\n".join(lines)


def check_start_quiz(state: dict, config: RunnableConfig) -> dict:
    """
    If the last message contains a start_quiz tool call, execute it and
    return the quiz state. Otherwise pass through unchanged.
    """
    messages = state.get("messages", [])
    if not messages:
        return {}
    last_msg = messages[-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        for tc in last_msg.tool_calls:
            if tc.get("name") == "start_quiz":
                args = tc.get("args", {})
                # Call the tool function directly
                from tutor.tools import start_quiz
                result = start_quiz(**args)
                if "error" not in result:
                    # Merge the quiz state into the current state
                    return result
    return {}  # No start_quiz found, proceed to tool_executor
    


def quiz_prepare(state: dict, config: RunnableConfig) -> dict:
    """
    Load quiz questions and initialise quiz state.
    Runs once at the start of a quiz.
    """
    chapter = state.get("quiz_chapter_id")
    questions = _load_questions(chapter)
    if not questions:
        logger.warning("quiz_prepare: no questions found")
        # Cancel quiz
        return {"quiz_requested": False, "quiz_active": False}

    # Select QUIZ_QUESTIONS_PER_QUIZ questions (randomly if more available)
    if len(questions) > QUIZ_QUESTIONS_PER_QUIZ:
        questions = random.sample(questions, QUIZ_QUESTIONS_PER_QUIZ)

    logger.info(f"quiz_prepare: loaded {len(questions)} questions")
    return {
        "quiz_questions": questions,
        "quiz_total": len(questions),
        "quiz_index": 0,
        "quiz_score": 0,
        "quiz_active": True,
        "quiz_awaiting_answer": False,   # will be set by quiz_ask
        "quiz_requested": False,         # consumed
        "context_messages": state.get("context_messages", []),  # keep existing
    }


def quiz_ask(state: dict, config: RunnableConfig) -> dict:
    """
    Send the current question to the user.
    """
    questions = state.get("quiz_questions", [])
    idx = state.get("quiz_index", 0)
    total = state.get("quiz_total", 0)

    if idx >= total:
        logger.error("quiz_ask: index out of range")
        return {}

    q = questions[idx]
    formatted = _format_question(q, idx, total)
    logger.info(f"quiz_ask: asking Q{idx+1}/{total}")

    return {
        "messages": [AIMessage(content=formatted)],
        "quiz_awaiting_answer": True,
    }


def quiz_store_answer(state: dict, config: RunnableConfig) -> dict:
    """
    Store the user's answer without grading.
    If all questions answered, the next routing step will call the LLM evaluator.
    """
    questions = state.get("quiz_questions", [])
    idx = state.get("quiz_index", 0)
    total = state.get("quiz_total", 0)
    quiz_answers = state.get("quiz_answers", [])

    if idx >= total:
        logger.error("quiz_store_answer: index out of range")
        return {}

    q = questions[idx]
    user_answer = state.get("user_question", "").strip()

    # Build a record of this Q&A
    record = {
        "question_id": q.get("question_id"),
        "type": q.get("type", ""),
        "question": q.get("question", ""),
        "options": q.get("options", []),
        "correct_answer": q.get("answer", ""),
        "explanation": q.get("explanation", ""),
        "user_answer": user_answer,
    }
    quiz_answers.append(record)

    logger.info(f"quiz_store_answer: Q{idx+1} stored")

    return {
        "quiz_answers": quiz_answers,
        "quiz_awaiting_answer": False,
        "quiz_index": idx + 1,
        # Don't send any feedback message – keep the interaction silent
    }

def quiz_llm_evaluate(state: dict, config: RunnableConfig) -> dict:
    """
    Final LLM evaluation: send all questions + user answers to the LLM,
    get back a score breakdown and insights.
    """
    quiz_answers = state.get("quiz_answers", [])
    total = len(quiz_answers)

    if total == 0:
        return {"quiz_active": False, "quiz_answers": []}

    # Build the evaluation prompt
    prompt_lines = [
        "You are a tutor evaluating a student's quiz. Below are the questions, the student's answers, and the correct answers.",
        "For each question, decide if the student's answer is essentially correct. Be lenient with wording, spelling, and minor variations.",
        "Then provide:",
        "- A total score (X out of Y).",
        "- A brief remark for each question (what they got right/wrong, and why).",
        "- Overall insights: what concepts they understand well, what needs review.",
        "",
        "Format your response naturally, like a tutor giving feedback. Do NOT use JSON.",
        "",
    ]
    for i, a in enumerate(quiz_answers, 1):
        prompt_lines.append(f"Q{i} ({a['type']}): {a['question']}")
        if a["options"]:
            prompt_lines.append(f"Options: {', '.join(a['options'])}")
        prompt_lines.append(f"Your answer: {a['user_answer']}")
        prompt_lines.append(f"Correct answer: {a['correct_answer']}")
        if a["explanation"]:
            prompt_lines.append(f"Explanation: {a['explanation']}")
        prompt_lines.append("")

    prompt_lines.append("Please evaluate now.")

    evaluation_prompt = "\n".join(prompt_lines)

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from tutor.config import TEMPERATURE, get_api_key, MODEL_NAME

        llm = ChatGoogleGenerativeAI(
            model=MODEL_NAME,
            temperature=0.2,  # slight variability for natural feedback
            google_api_key=get_api_key(),
        )
        response = llm.invoke([HumanMessage(content=evaluation_prompt)])
        feedback = response.content
        if isinstance(feedback, list):
            feedback = " ".join(
                block["text"] for block in feedback if isinstance(block, dict) and "text" in block
            )
        feedback = feedback.strip()
    except Exception as exc:
        logger.error(f"quiz_llm_evaluate: LLM call failed ({exc})")
        feedback = "Sorry, I couldn't evaluate your quiz. Please try again."

    logger.info(f"quiz_llm_evaluate: generated feedback ({len(feedback)} chars)")

    # Reset quiz state
    return {
        "messages": [AIMessage(content=feedback)],
        "quiz_active": False,
        "quiz_awaiting_answer": False,
        "quiz_questions": [],
        "quiz_answers": [],
        "quiz_index": 0,
        "quiz_score": 0,
        "quiz_total": 0,
        "quiz_chapter_id": None,
    }


def quiz_end(state: dict, config: RunnableConfig) -> dict:
    """
    Finish the quiz, display final score, and reset quiz state.
    """
    score = state.get("quiz_score", 0)
    total = state.get("quiz_total", 0)
    summary = (
        f"🎉 Quiz finished! You scored **{score}/{total}**.\n"
    )
    if total > 0 and score == total:
        summary += "Perfect score—great job!"
    elif total > 0 and score >= total/2:
        summary += "Good work! Review any missed concepts to strengthen your understanding."
    else:
        summary += "Keep studying! Want me to explain any of these concepts again?"

    logger.info(f"quiz_end: score {score}/{total}")

    return {
        "messages": [AIMessage(content=summary)],
        "quiz_active": False,
        "quiz_awaiting_answer": False,
        "quiz_questions": [],
        "quiz_index": 0,
        "quiz_score": 0,
        "quiz_total": 0,
        "quiz_chapter_id": None,
    }