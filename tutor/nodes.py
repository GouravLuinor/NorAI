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

import asyncio
import logging
import uuid
from pathlib import Path
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph.message import RemoveMessage
from langchain_core.runnables import RunnableConfig
from tutor.config import TEMPERATURE
from .prompts import build_system_prompt, build_context_block, build_image_context_block
from .retrieval_config import CONFIDENCE_THRESHOLD

logger = logging.getLogger(__name__)


# ── Phase 5 / P3.6: conversation summarization ────────────────────────────────
_SUMMARY_TRIGGER_MSG_COUNT = 12   # fire when 12+ messages (6 turns) exist
_SUMMARY_RETAIN_RECENT   = 6      # keep the most recent 6 messages untouched
_SUMMARY_PREFIX          = "CONVERSATION SUMMARY:"
# P3.6: character budget for the retained prompt window (~4 chars/token).
# A fixed message count alone is fragile — one enormous pasted answer would
# blow the context window. The retained window is the min(count, budget-fit).
_SUMMARY_RETAIN_CHAR_BUDGET = 8000

_SUMMARIZE_SYSTEM = """\
You are a note-taking assistant. Summarize the following tutoring conversation \
into a concise paragraph. Include:
- What topics were discussed.
- Any key questions the student asked and the answers given.
- The student's apparent level of understanding (if evident).
Keep the summary factual and brief — no more than 7 sentences."""

# ── load_memory (rebuilds the prompt window from the transcript) ─────────────

def _msg_char_count(m) -> int:
    """Rough character length of a message's content (LLM token proxy)."""
    content = m.content
    if isinstance(content, list):
        return sum(
            len(str(block.get("text", "")))
            for block in content if isinstance(block, dict)
        )
    return len(str(content))


def _recent_window(turns: list) -> list:
    """Suffix of `turns` to keep in the prompt window.

    P3.6: bounded by BOTH the fixed message count and a character budget, so a
    single very long message can't silently exceed the model context limit.
    Always keeps at least the single most recent message.
    """
    budgeted = 0
    total = 0
    for m in reversed(turns):
        c = _msg_char_count(m)
        if total + c > _SUMMARY_RETAIN_CHAR_BUDGET:
            break
        total += c
        budgeted += 1
    retain = max(1, min(_SUMMARY_RETAIN_RECENT, budgeted))
    return turns[-retain:]


def load_memory_node(state: dict, config: RunnableConfig) -> dict:
    """
    Rebuild the windowed conversation history used in the LLM prompt.

    The full transcript lives in state['messages'] (persisted by the
    checkpointer across turns). This node derives state['context_messages']
    from it every turn: the most recent summary SystemMessage (if any) plus
    the last _SUMMARY_RETAIN_RECENT Human/AI messages. This is what gives the
    model real conversational memory — previously context_messages was never
    populated, so the prompt contained only the current question.
    """
    messages = state.get("messages", [])
    if not messages:
        return {}

    summary = None
    turns: list = []
    for m in messages:
        if isinstance(m, SystemMessage):
            if m.content and str(m.content).startswith(_SUMMARY_PREFIX):
                summary = m  # keep only the most recent summary
        elif isinstance(m, (HumanMessage, AIMessage)):
            turns.append(m)

    recent = _recent_window(turns)
    context = ([summary] if summary is not None else []) + recent
    logger.debug(f"load_memory_node: window = {len(context)} messages ({len(recent)} recent, {'summary' if summary else 'no summary'})")
    return {"context_messages": context}


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


def verify_citations_node(state: dict, config: RunnableConfig) -> dict:
    """
    P3.3: post-check the answer's Sources citations against the chunks that were
    actually retrieved this turn. Deterministic (no LLM). Unverified citations
    are marked so the frontend never renders a fabricated reference.

    Reads:  state['answer'], state['retrieved_chunks']
    Writes: state['verified_citations']
    """
    from tutor.citations import verify_citations

    answer = state.get("answer", "")
    chunks = state.get("retrieved_chunks", [])
    verified = verify_citations(answer, chunks)
    logger.debug(f"verify_citations_node: {len(verified)} citations "
                 f"({sum(1 for c in verified if c['verified'])} verified)")
    return {"verified_citations": verified}


# ── generate_answer (Phase 3: context injection) ───────────────────────────────
async def generate_answer_node(state: dict, config: RunnableConfig, output_dir: str | None = None) -> dict:
    """
    Core LLM node. Builds the full prompt, calls Gemini, records the answer.

    Prompt structure (uncached, default):
        [SystemMessage] Tutor system prompt + lecture title
        [SystemMessage] CONTEXT block (retrieved study-note chunks)
        [SystemMessage] IMAGE CONTEXT block (retrieved screenshots)   ← Phase 4
        [HumanMessage / AIMessage] Conversation history (all prior turns)
        [HumanMessage] Current user question

    P7.x context caching (optional, when `output_dir` is given):
        The static prefix — system prompt + persona + conversation summary —
        is stored in a Gemini context cache (tutor/cache.py). When a cache is
        active, the request sends ONLY the dynamic suffix (context block,
        image context, recent window, question) and NO SystemMessages, because
        LangChain merges SystemMessages into `system_instruction` which would
        duplicate/conflict with the cached prefix. Quality is unchanged: the
        cached system_instruction still leads the prompt. If the cache is
        unavailable (below the 4096-token minimum, API error), this falls back
        to the exact uncached structure above — a caching hiccup can never
        change the answer.

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
    study_mode = state.get("study_mode", "default")
    persona_instructions = state.get("persona_instructions", "")
    system_prompt = build_system_prompt(lecture_title, mode=study_mode)
    
    # Phase 5: check if all retrieved chunks are weak matches
    low_confidence = (
        retrieved_chunks
        and all(c.get("distance", 1.0) > CONFIDENCE_THRESHOLD for c in retrieved_chunks)
    )
    # P3.7: retrieval_status ∈ {"ok","empty","error"} — "error" tells the model
    # retrieval infra failed (don't fabricate lecture content); "empty" and
    # "ok" keep the existing no-context / low-confidence notes.
    retrieval_status = state.get("retrieval_status", "ok")
    context_block = build_context_block(
        retrieved_chunks, low_confidence=low_confidence, status=retrieval_status
    )
    
    image_context_block = build_image_context_block(retrieved_images)   # ← Phase 4


    # Old filter logic: removed
    # conversational_history = [m for m in messages if not isinstance(m, SystemMessage) ...]
    
    # Use the windowed context messages (summary + recent) for prompt history.
    # The ephemeral SystemMessages (prompt, context blocks) are already excluded
    # because context_messages only contains HumanMessage, AIMessage, and summary SystemMessages.
    conversational_history = state.get("context_messages", [])

    # ── P7.x context caching (rolling prefix) ──────────────────────────────────
    # The static prefix = system prompt + persona + conversation summary. It is
    # cached per lecture (keyed by the output dir basename) and refreshed
    # whenever the summary changes. When the cache is active we send ONLY the
    # dynamic suffix, with no SystemMessages (see docstring).
    cache_name = None
    if output_dir:
        try:
            from tutor import cache as tutor_cache

            # Extract the rolling summary from the windowed history (if any).
            summary_text = ""
            for m in conversational_history:
                if isinstance(m, SystemMessage) and m.content and str(m.content).startswith(_SUMMARY_PREFIX):
                    summary_text = str(m.content)
                    break

            lecture_key = Path(output_dir).name
            system_text, contents_text = tutor_cache.build_cache_parts(
                system_prompt, persona_instructions, summary_text, output_dir
            )
            # get_or_create_prefix_cache may hit the network (create/list);
            # run it off the event loop so the async node never blocks on it.
            cache_name = await asyncio.to_thread(
                tutor_cache.get_or_create_prefix_cache,
                lecture_key,
                system_text,
                contents_text,
            )
        except Exception:  # noqa: BLE001
            logger.debug("generate_answer_node: cache setup failed, using uncached", exc_info=True)
            cache_name = None

    if cache_name:
        # Cached path: no SystemMessages (they'd merge into system_instruction
        # and duplicate the cached prefix). The recent window excludes the
        # summary — it already lives in the cache's system_instruction.
        recent = [
            m for m in conversational_history
            if isinstance(m, (HumanMessage, AIMessage))
        ]
        prompt_messages = [
            HumanMessage(content=context_block),
            *([HumanMessage(content=image_context_block)] if image_context_block else []),
            *recent,
            HumanMessage(content=user_question),
        ]
    else:
        prompt_messages = [
            SystemMessage(content=system_prompt),
            *([SystemMessage(content=persona_instructions)] if persona_instructions else []),
            SystemMessage(content=context_block),
            *([SystemMessage(content=image_context_block)] if image_context_block else []),  # ← Phase 4: only include if non-empty
            *conversational_history,
            HumanMessage(content=user_question),
        ]

    # ── LLM call ───────────────────────────────────────────────────────────────
    # P6.1: stream the answer via llm.astream so a graph-level
    # `astream_events(version="v2")` actually surfaces per-token
    # `on_chat_model_stream` events from generate_answer_node. The chunked text
    # is accumulated here for the committed state; the tokens the user sees come
    # from the event stream, not this string.
    from tutor.llm import make_chat_llm
    llm = make_chat_llm(
        node="generate_answer_node",
        temperature=TEMPERATURE,
        cached_content=cache_name,
    )

    # Extract text if the chunk content is a list of blocks (handling
    # 'thinking' models): append the block's "text" fragments in stream order.
    # P0 fix: guard the stream — an unguarded Gemini outage used to kill the
    # whole turn mid-flight, leaving the SSE client without a final frame.
    text_parts: list[str] = []
    try:
        async for chunk in llm.astream(prompt_messages):
            content = chunk.content
            if isinstance(content, str):
                if content:
                    text_parts.append(content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("text"):
                        text_parts.append(block["text"])
    except Exception:
        logger.exception("generate_answer_node: LLM stream failed")
        text_parts.append(
            "I couldn't reach the AI service just now. Please try again in a moment."
        )
    answer_text = "".join(text_parts)

    logger.debug(f"generate_answer_node: answered ({len(answer_text)} chars)")

    # ── Update state ───────────────────────────────────────────────────────────
    # add_messages reducer appends both messages to the persisted list.
    # We do NOT store the SystemMessages — they're rebuilt from state each turn.
    import uuid
    message_id = state.get("message_id") or str(uuid.uuid4())
    ai_id = f"ai-{message_id}"

    return {
        "messages": [
            HumanMessage(content=user_question, id=message_id),
            AIMessage(content=answer_text, id=ai_id),
        ],
        "answer": answer_text,
    }


# ── save_memory (incremental summarization) ───────────────────────────────────

async def save_memory_node(state: dict, config: RunnableConfig) -> dict:
    """
    Phase 5 / P3.6: condense old turns into a summary record and REMOVE the
    original messages from the persisted transcript once enough NEW turns have
    accumulated since the last summary.

    P3.6 hardening over the original design:
      - The summarised messages are deleted from state via RemoveMessage, so the
        checkpoint DB no longer grows unboundedly — the transcript stays
        approximately `_SUMMARY_TRIGGER_MSG_COUNT` messages long instead of
        accumulating forever (the prompt window was already bounded, the store
        wasn't).
      - The retained recent window is bounded by a character budget in addition
        to the fixed message count (see _recent_window), protecting the context
        window from single oversized messages.

    Trigger: when the number of Human/AI messages AFTER the last summary
    record exceeds _SUMMARY_TRIGGER_MSG_COUNT. Keeps the most recent window
    untouched; summarises the rest.
    """
    messages = state.get("messages", [])
    if not messages:
        return {}

    # Find the index of the most recent summary record in the transcript
    last_summary_idx = -1
    for idx, m in enumerate(messages):
        if isinstance(m, SystemMessage) and m.content and str(m.content).startswith(_SUMMARY_PREFIX):
            last_summary_idx = idx

    pending = [m for m in messages[last_summary_idx + 1:] if isinstance(m, (HumanMessage, AIMessage))]
    if len(pending) <= _SUMMARY_TRIGGER_MSG_COUNT:
        logger.debug("save_memory_node: no summarization needed")
        return {}

    recent = _recent_window(pending)
    split_idx = len(pending) - len(recent)
    to_summarise = pending[:split_idx]

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
    summarised = False
    try:
        from tutor.llm import make_chat_llm
        llm = make_chat_llm(node="save_memory_node", temperature=0.0)
        response = await llm.ainvoke([
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
        summarised = bool(summary_text)
    except Exception as exc:
        logger.error(f"save_memory_node: summarisation failed ({exc})")
        summary_text = "[Earlier conversation truncated.]"

    summary_msg = SystemMessage(content=f"{_SUMMARY_PREFIX}\n{summary_text}")

    # P3.6/P2.5: remove the summarised messages from the persisted transcript
    # ONLY when the LLM actually produced a summary. On a Gemini outage the
    # originals MUST stay — deleting them and keeping a placeholder would be
    # permanent transcript loss. Next turn simply retries the summarisation.
    if summarised:
        removals = [
            RemoveMessage(id=m.id)
            for m in to_summarise
            if getattr(m, "id", None)
        ]
    else:
        removals = []

    # Append the summary as a record in the transcript so load_memory_node can
    # pick it up next turn. The UI filters SystemMessages out of the response.
    return {"messages": removals + [summary_msg]}
