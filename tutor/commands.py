"""Command execution nodes – no LLM involved."""

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def execute_command(state: dict, config: RunnableConfig) -> dict:
    """Run the appropriate tool based on command_type."""
    cmd = state.get("command_type", "")
    chapter_id = state.get("chapter_id")

    if cmd == "quiz":
        from tutor.tools import start_quiz
        result = start_quiz(chapter_id)
        if "error" in result:
            return {
                "messages": [AIMessage(content=result["error"])],
                "is_command": False,
                "command_type": "",
            }
        # Merge quiz state and start the quiz loop
        result["is_command"] = False
        result["command_type"] = ""
        return result

    elif cmd == "summary":
        from tutor.tools import show_summary
        if chapter_id is None:
            msg = "Which chapter would you like me to summarize?"
        else:
            msg = show_summary(chapter_id)
        return {
            "messages": [AIMessage(content=msg)],
            "answer": msg,
            "is_command": False,
            "command_type": "",
        }

    elif cmd == "flashcards":
        from tutor.tools import show_flashcards
        msg = show_flashcards(chapter_id)
        return {
            "messages": [AIMessage(content=msg)],
            "answer": msg,
            "is_command": False,
            "command_type": "",
        }

    # Fallback
    return {"is_command": False, "command_type": ""}