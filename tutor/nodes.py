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

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.runnables import RunnableConfig
from tutor.config import MODEL_NAME, TEMPERATURE, get_api_key
from .prompts import build_system_prompt, build_context_block, build_image_context_block

logger = logging.getLogger(__name__)


# ── load_memory (no-op, kept for topology stability) ──────────────────────────

def load_memory_node(state: dict, config: RunnableConfig) -> dict:
    """
    Intentional no-op. LangGraph's checkpointer already restores state.
    Future: load conversation summary, prime retrieved_chunks for multi-hop, etc.
    """
    logger.debug("load_memory_node: no-op")
    return {}


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
    context_block = build_context_block(retrieved_chunks)
    image_context_block = build_image_context_block(retrieved_images)   # ← Phase 4

    # Filter out any SystemMessages already in the persisted history
    # (the base system prompt and context blocks are rebuilt fresh each turn)
    conversational_history = [m for m in messages if not isinstance(m, SystemMessage)]

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
    Intentional no-op. LangGraph's checkpointer already persists state.
    Future: conversation summarisation to bound context window growth.
    """
    logger.debug("save_memory_node: no-op")
    return {}

