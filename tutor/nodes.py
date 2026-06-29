"""
nodes.py (Phase 3 — replace your existing tutor/nodes.py with this)

Changes from Phase 1/2:
  - generate_answer_node now reads state['retrieved_chunks'] and injects a
    formatted CONTEXT block into the prompt via build_context_block().
  - load_memory_node and save_memory_node are unchanged (still logged no-ops).

The context block is injected as a SystemMessage AFTER the tutor system prompt
and BEFORE the conversation history. This puts it in the LLM's "permanent
instructions" slot without polluting the conversation turns, and means it
won't be summarised away if we add a history-condensing step later.
"""

from __future__ import annotations

import logging
from pathlib import Path
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.runnables import RunnableConfig
from tutor.config import MODEL_NAME, TEMPERATURE, get_api_key
from .prompts import build_system_prompt, build_context_block, build_image_context_block
from .retrieval_config import CONFIDENCE_THRESHOLD

logger = logging.getLogger(__name__)


# ── Phase 5: conversation summarization ────────────────────────────────────────
_SUMMARY_TRIGGER_MSG_COUNT = 12   # fire when 12+ messages (6 turns) exist
_SUMMARY_RETAIN_RECENT   = 6      # keep the most recent 6 messages untouched
_SUMMARY_PREFIX          = "CONVERSATION SUMMARY:"

_SUMMARIZE_SYSTEM = """\
You are a note-taking assistant. Summarize the following tutoring conversation \
into a concise paragraph. Include:
- What topics were discussed.
- Any key questions the student asked and the answers given.
- The student's apparent level of understanding (if evident).
Keep the summary factual and brief — no more than 5 sentences."""

def chapter_summary_node(state: dict, config: RunnableConfig) -> dict:
    """
    Load the pre-made revision summary for a chapter and return it as the answer.

    Reads:  state['summary_chapter_id']
    Writes: state['answer'], state['messages'], clears summary flags
    """
    chapter_id = state.get("summary_chapter_id")
    if chapter_id is None:
        # Fallback: try the current chapter_id from conversation
        chapter_id = state.get("chapter_id")

    if chapter_id is None:
        msg = "Which chapter would you like me to summarize?"
        return {
            "messages": [AIMessage(content=msg)],
            "answer": msg,
            "summary_requested": False,
        }

    path = Path(f"outputs/revision/revision_chapter_{chapter_id}.md")
    if not path.exists():
        msg = f"Sorry, I don't have a summary for chapter {chapter_id}."
        return {
            "messages": [AIMessage(content=msg)],
            "answer": msg,
            "summary_requested": False,
        }

    content = path.read_text(encoding="utf-8")
    logger.info(f"chapter_summary_node: loaded summary for chapter {chapter_id}")

    return {
        "messages": [AIMessage(content=content)],
        "answer": content,
        "summary_requested": False,
        "summary_chapter_id": None,
    }

# ── load_memory (no-op, kept for topology stability) ──────────────────────────

def load_memory_node(state: dict, config: RunnableConfig) -> dict:
    """
    Intentional no-op. LangGraph's checkpointer already restores state.
    Future: load conversation summary, prime retrieved_chunks for multi-hop, etc.
    """
    logger.debug("load_memory_node: no-op")
    return {}


def _build_low_confidence_context_block(chunks: list[dict]) -> str:
    """
    Same as build_context_block but uses the low-confidence note instead
    of the standard header, telling the model the retrieved passages are
    weak matches and to express appropriate uncertainty.
    """
    # Import here to avoid circular import, or move _LOW_CONFIDENCE_NOTE to a shared location.
    # Actually, it's cleaner to just inline the logic.
    from .prompts import _LOW_CONFIDENCE_NOTE as note
    
    lines = ["--- CONTEXT ---", note, ""]
    for i, chunk in enumerate(chunks, 1):
        path = chunk.get("heading_path") or chunk.get("heading") or "Unknown section"
        text = chunk.get("text", "").strip()
        dist = chunk.get("distance", 0.0)
        lines.append(f"[{i}] Section: {path}  (relevance: {dist:.3f})")
        lines.append(text)
        lines.append("")
    lines.append("--- END CONTEXT ---")
    return "\n".join(lines)


# ── generate_answer (Phase 3: context injection) ───────────────────────────────

def generate_answer_node(state: dict, config: RunnableConfig) -> dict:
    """
    Core LLM node. Builds the full prompt, calls Gemini, records the answer.

    Prompt structure:
        [SystemMessage] Tutor system prompt + lecture title
        [SystemMessage] CONTEXT block (retrieved study-note chunks)
        [SystemMessage] IMAGE CONTEXT block (retrieved screenshots)   ← Phase 4
        [HumanMessage / AIMessage] Conversation history (all prior turns)
        [HumanMessage] Current user question

    Why separate SystemMessages?
        The context blocks change every turn (different retrieved chunks/images).
        By keeping them separate from the base system prompt, we can see clearly
        in logs which part changed, and a future summarisation node won't try to
        compress them (they're already per-turn ephemeral).

    Reads:
        state['lecture_title']     → system prompt
        state['retrieved_chunks']  → text context block
        state['retrieved_images']  → image context block   ← Phase 4
        state['messages']          → conversation history
        state['user_question']     → current question

    Writes:
        state['messages']  (appended via add_messages: HumanMessage + AIMessage)
        state['answer']    (plain string, current turn)
    """
    lecture_title = state.get("lecture_title", "")
    retrieved_chunks = state.get("retrieved_chunks", [])
    retrieved_images = state.get("retrieved_images", [])      # ← Phase 4

    if retrieved_images:
        logger.info(f"generate_answer_node: got {len(retrieved_images)} images: {[img.get('section') for img in retrieved_images]}")
    else:
        logger.info("generate_answer_node: no images retrieved")

        
    messages = state.get("messages", [])
    user_question = state.get("user_question", "")

    if not user_question:
        logger.warning("generate_answer_node: no user_question in state")
        return {}
    
    # ── Build prompt ───────────────────────────────────────────────────────────
    system_prompt = build_system_prompt(lecture_title)
    
    # Phase 5: check if all retrieved chunks are weak matches
    low_confidence = (
        retrieved_chunks
        and all(c.get("distance", 1.0) > CONFIDENCE_THRESHOLD for c in retrieved_chunks)
    )
    context_block = build_context_block(retrieved_chunks, low_confidence=low_confidence)
    
    image_context_block = build_image_context_block(retrieved_images)   # ← Phase 4


    # Old filter logic: removed
    # conversational_history = [m for m in messages if not isinstance(m, SystemMessage) ...]
    
    # Use the windowed context messages (summary + recent) for prompt history.
    # The ephemeral SystemMessages (prompt, context blocks) are already excluded
    # because context_messages only contains HumanMessage, AIMessage, and summary SystemMessages.
    conversational_history = state.get("context_messages", [])

    prompt_messages = [
        SystemMessage(content=system_prompt),
        SystemMessage(content=context_block),
        *([SystemMessage(content=image_context_block)] if image_context_block else []),  # ← Phase 4: only include if non-empty
        *conversational_history,
        HumanMessage(content=user_question),
    ]

    # ── LLM call ───────────────────────────────────────────────────────────────
    llm = ChatGoogleGenerativeAI(
        model=MODEL_NAME,
        temperature=TEMPERATURE,
        google_api_key=get_api_key(),
    )

    response = llm.invoke(prompt_messages)
        
    # Extract text if the response is a list of blocks (handling 'thinking' models)
    if isinstance(response.content, list):
        text_blocks = [block["text"] for block in response.content if isinstance(block, dict) and "text" in block]
        answer_text = "\n".join(text_blocks)
    else:
        answer_text = response.content

    logger.debug(f"generate_answer_node: answered ({len(answer_text)} chars)")

    # ── Update state ───────────────────────────────────────────────────────────
    # add_messages reducer appends both messages to the persisted list.
    # We do NOT store the SystemMessages — they're rebuilt from state each turn.
    return {
        "messages": [
            HumanMessage(content=user_question),
            AIMessage(content=answer_text),
        ],
        "answer": answer_text,
    }


# ── save_memory (no-op, kept for topology stability) ──────────────────────────

def save_memory_node(state: dict, config: RunnableConfig) -> dict:
    """
    Phase 5: Build a windowed conversation history (summary + recent messages)
    and store it in state['context_messages']. The full transcript remains in
    state['messages'] but is not used in the prompt.

    Trigger: when state['context_messages'] reaches _SUMMARY_TRIGGER_MSG_COUNT.
    """
    context_msgs: list = state.get("context_messages", [])
    if len(context_msgs) <= _SUMMARY_TRIGGER_MSG_COUNT:
        logger.debug("save_memory_node: no summarization needed")
        return {}

    split_idx = len(context_msgs) - _SUMMARY_RETAIN_RECENT
    to_summarise = context_msgs[:split_idx]
    recent = context_msgs[split_idx:]

    logger.info(
        f"save_memory_node: summarising {len(to_summarise)} older messages "
        f"({len(recent)} recent messages preserved)"
    )

    # Build transcript
    transcript_lines: list[str] = []
    for m in to_summarise:
        role = "Student" if isinstance(m, HumanMessage) else "Tutor"
        content = m.content
        if isinstance(content, list):
            content = " ".join(
                block.get("text", "") for block in content if isinstance(block, dict)
            )
        transcript_lines.append(f"{role}: {content}")
    transcript_str = "\n".join(transcript_lines)

    # Summarise via LLM
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from tutor.config import TEMPERATURE, get_api_key, MODEL_NAME

        llm = ChatGoogleGenerativeAI(
            model=MODEL_NAME,
            temperature=0.0,
            google_api_key=get_api_key(),
        )
        response = llm.invoke([
            SystemMessage(content=_SUMMARIZE_SYSTEM),
            HumanMessage(content=transcript_str),
        ])
        summary_text = response.content
        if isinstance(summary_text, list):
            summary_text = " ".join(
                block["text"] for block in summary_text
                if isinstance(block, dict) and "text" in block
            )
        summary_text = summary_text.strip()
    except Exception as exc:
        logger.error(f"save_memory_node: summarisation failed ({exc})")
        summary_text = "[Earlier conversation truncated.]"

    summary_msg = SystemMessage(content=f"{_SUMMARY_PREFIX}\n{summary_text}")

    # New context window: summary + recent messages
    new_context = [summary_msg] + recent

    # Also update the full messages list by appending the summary (as a record)
    # but without the duplicates — we'll just append the summary.
    return {
        "context_messages": new_context,
        "messages": [summary_msg],  # add summary to full transcript as a record
    }
