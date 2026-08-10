"""
nodes_retrieval.py — Phase 3 graph nodes: query rewriting + retrieval.

Two new nodes added between load_memory and generate_answer:

    START
      └─ load_memory
          └─ rewrite_query      ← NEW: improves retrieval recall
              └─ retrieve        ← NEW: queries Chroma, fills retrieved_chunks
                  └─ generate_answer
                      └─ save_memory
                          └─ END

Why rewrite_query?
    The user's raw question is often conversational and refers to prior context
    ("what did you mean by that?", "can you elaborate?"). The embedding model
    has no conversational context — it embeds the query in isolation. Rewriting
    turns it into a self-contained, retrieval-optimised search query before it
    hits Chroma.

    The rewrite is lightweight: it calls the LLM with a short prompt and the
    last N turns of history. No tool calls, no streaming.

Why keep it as a separate node (not inline in retrieve)?
    Same reason load_memory/save_memory were kept separate in Phase 1: topology
    stability. If we ever want to add a "query routing" node (decide whether to
    retrieve at all), or run rewrite + retrieve in parallel branches, we can
    rewire the graph without touching the rewrite or retrieve implementations.

Phase 3.5 — cross-turn chapter state:
    detect_chapter_node also writes `last_chapter_id` to the graph state whenever
    the user names a chapter explicitly. On later turns an anaphoric follow-up
    ("what about that?", "explain it", "why is that?") re-uses the remembered
    chapter, so retrieval stays scoped to the chapter the student is in the
    middle of. A brand-new question without anaphora goes back to a full-index
    search, so genuinely cross-chapter questions are never blocked.
"""

from __future__ import annotations
import re
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from .retriever import IndexNotBuiltError, retrieve, retrieve_images
from .retrieval_config import TOP_K, TOP_K_IMAGES, CONFIDENCE_THRESHOLD
logger = logging.getLogger(__name__)

# How many recent messages to include as context for the rewrite prompt.
# Enough to resolve pronouns / back-references without ballooning the prompt.
_REWRITE_HISTORY_TURNS = 3  # turns = human+AI pairs, so 6 messages max

_REWRITE_SYSTEM = """\
You are a search-query optimiser for a student study tool.
Your only job: rewrite the student's question into a self-contained search query.

Rules:
- Output ONLY the rewritten query. No preamble, no explanation, no quotes.
- If the question references prior conversation, resolve the reference using
  the history provided.
- Do NOT broaden the scope of the question. If they ask "what is X?", search
  for "X definition" — don't add "properties", "use cases", or other topics.
- If the question is already a good search query, return it unchanged.
- Maximum 1 sentence.
"""

# ── Chapter detection (Phase 5) ───────────────────────────────────────────────

# Word-to-number mapping for spelled-out ordinals
_WORD_TO_NUM = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
}

_QUIZ_KEYWORDS = ["quiz", "quizzes", "test me", "ask me questions", "give me a quiz",
                  "start a quiz", "question me", "pop quiz"]
_SUMMARY_KEYWORDS = ["summarize", "summarise", "summary", "overview", "recap"]
_FLASHCARD_KEYWORDS = ["flashcard", "flashcards", "flash card", "show me cards", "study cards"]

_QUIZ_PATTERN = re.compile(r"\b(" + "|".join(_QUIZ_KEYWORDS) + r")\b", re.IGNORECASE)
_SUMMARY_PATTERN = re.compile(r"\b(" + "|".join(_SUMMARY_KEYWORDS) + r")\b", re.IGNORECASE)
_FLASHCARD_PATTERN = re.compile(r"\b(" + "|".join(_FLASHCARD_KEYWORDS) + r")\b", re.IGNORECASE)

# Regex patterns: ordered most-specific-first. First match wins.
_CHAPTER_REGEXES = [
    (re.compile(r"\bchapter\s+(\d+)\b", re.IGNORECASE), lambda m: int(m.group(1))),
    (re.compile(r"\bch(?:apter|apte|apt|ap)[.\s]*(\d+)\b", re.IGNORECASE), lambda m: int(m.group(1))),
    (re.compile(r"\bch\s*(\d+)\b", re.IGNORECASE), lambda m: int(m.group(1))),
    (re.compile(r"\bthe\s+(\w+)\s+chapter\b", re.IGNORECASE),
     lambda m: _WORD_TO_NUM.get(m.group(1).lower())),
]

# P3.5: anaphoric follow-ups resolve against the last explicitly-referenced
# chapter. Conservative phrase list — a bare noun (e.g. "What is a stack?") is
# NOT anaphoric, so genuinely new cross-chapter questions stay unfiltered.
_ANAPHORIC_RE = re.compile(
    r"^\s*("
    r"what about|how about|"
    r"what does that|what is that|what are those|what do you mean|"
    r"why is that|why does that|why do(es)? (it|they|those|that)|"
    r"how does (it|that|this)|how is that|"
    r"explain (that|this|it|more)|elaborate( on)? (that|this|it)|"
    r"tell me more|more (about|on) (that|this|it)|"
    r"can you (explain|clarify|go over|repeat) (that|this|it)|"
    r"does (that|this|it)|is (that|this|it)|"
    r"and what happens (next|then)|what does it (do|mean)"
    r")\b",
    re.IGNORECASE,
)


def _extract_chapter_id(text: str) -> int | None:
    """Return chapter number if the text contains an explicit chapter reference."""
    for pattern, extractor in _CHAPTER_REGEXES:
        match = pattern.search(text)
        if match:
            num = extractor(match)
            if num is not None:
                return num
    return None


def _is_anaphoric(question: str) -> bool:
    """True when the question is a follow-up to prior context (so it should keep
    the last explicitly-referenced chapter's retrieval scope)."""
    return bool(_ANAPHORIC_RE.match(question.strip()))


def detect_chapter_node(state: dict, config: RunnableConfig) -> dict:
    question = state.get("user_question", "")
    explicit = _extract_chapter_id(question)
    last_chapter = state.get("last_chapter_id")

    # P3.5 cross-turn state:
    #  - explicit ref → scope THIS turn + remember it as last_chapter_id.
    #  - anaphoric follow-up with a remembered chapter → reuse it.
    #  - otherwise → full-index search (no filter), keep last_chapter_id.
    if explicit is not None:
        chapter_id = explicit
    elif last_chapter is not None and _is_anaphoric(question):
        chapter_id = last_chapter
    else:
        chapter_id = None

    result: dict = {
        "chapter_id": chapter_id,
        "is_command": False,
        "command_type": "",          # "quiz", "summary", or "flashcards"
    }
    if explicit is not None:
        result["last_chapter_id"] = explicit

    if _QUIZ_PATTERN.search(question):
        result["is_command"] = True
        result["command_type"] = "quiz"
        logger.info(f"Quiz command detected (chapter {chapter_id})")
    elif _SUMMARY_PATTERN.search(question):
        result["is_command"] = True
        result["command_type"] = "summary"
        logger.info(f"Summary command detected (chapter {chapter_id})")
    elif _FLASHCARD_PATTERN.search(question):
        result["is_command"] = True
        result["command_type"] = "flashcards"
        logger.info(f"Flashcard command detected (chapter {chapter_id})")

    return result

# Add to existing nodes_retrieval.py

def retrieve_images_node(state: dict, config: RunnableConfig, output_dir=None) -> dict:
    """
    Retrieve relevant screenshots using the rewritten search query or user question.
    Uses the process-wide singleton retriever from tutor.retriever.
    """
    query = state.get("search_query") or state.get("user_question", "")
    chapter_id = state.get("chapter_id")
    
    retrieved_images: list = []
    try:
        retrieved_images = retrieve_images(
            query=query,
            chapter_id=chapter_id,
            k=TOP_K_IMAGES,
            output_dir=output_dir,
        )
    except Exception:
        logger.error("[retrieve_images_node] Unexpected error:", exc_info=True)
    
    return {"retrieved_images": retrieved_images}

async def rewrite_query_node(state: dict, config: RunnableConfig) -> dict:
    """
    LangGraph node: rewrite state['user_question'] into a retrieval-optimised query.

    Reads:  state['user_question'], state['messages'] (recent history)
    Writes: state['search_query'] (the rewritten query)
            state['retrieved_chunks'] = []  (clear any stale chunks from prior turn)
            state['retrieved_images'] = []  (clear any stale images from prior turn)
    """
    question = state.get("user_question", "")
    if not question:
        logger.warning("rewrite_query_node: no user_question in state, skipping rewrite")
        return {"retrieved_chunks": [], "retrieved_images": []}

    # Pull recent history for context (exclude SystemMessages — they're not
    # conversational context, just the tutor prompt rebuilt each turn)
    all_messages = state.get("messages", [])
    conversational = [m for m in all_messages if not isinstance(m, SystemMessage)]
    recent = conversational[-(_REWRITE_HISTORY_TURNS * 2) :]  # last N turns

    # Build a compact history snippet for the rewrite prompt
    history_lines = []
    for m in recent:
        if isinstance(m, HumanMessage):
            history_lines.append(f"Student: {m.content}")
        else:
            history_lines.append(f"Tutor: {m.content}")
    history_str = "\n".join(history_lines) if history_lines else "(no prior conversation)"

    # P3.5: keep the chapter scope visible to the rewriter so anaphoric
    # follow-ups stay resolvable even after the question is de-referenced.
    active_chapter = state.get("chapter_id") or state.get("last_chapter_id")
    chapter_hint = ""
    if active_chapter:
        chapter_hint = f"\nThe student is currently focused on chapter {active_chapter}."

    rewrite_prompt = (
        f"Conversation so far:\n{history_str}{chapter_hint}\n\n"
        f"Student's latest question: {question}\n\n"
        f"Rewritten search query:"
    )

    try:
        from tutor.llm import make_chat_llm

        llm = make_chat_llm(
            node="rewrite_query_node",
            model=_get_model_from_config(),
            temperature=0.0,  # rewrite should be deterministic
        )
    except Exception as exc:
        logger.warning(f"rewrite_query_node: LLM init failed ({exc}), using raw question")
        return {"search_query": question, "retrieved_chunks": [], "retrieved_images": []}

    try:
        response = await llm.ainvoke(
            [SystemMessage(content=_REWRITE_SYSTEM), HumanMessage(content=rewrite_prompt)]
        )
        content = response.content
        if isinstance(content, list):
            text_blocks = [block["text"] for block in content if isinstance(block, dict) and "text" in block]
            content = "\n".join(text_blocks)
            
        rewritten = content.strip()

        if rewritten:
            logger.debug(f"Query rewrite: {question!r} → {rewritten!r}")
            return {"search_query": rewritten, "retrieved_chunks": [], "retrieved_images": []}
    except Exception as exc:
        logger.warning(f"rewrite_query_node: LLM call failed ({exc}), using raw question")

    return {"search_query": question, "retrieved_chunks": [], "retrieved_images": []}


def _get_model_from_config() -> str:
    """Fallback: read MODEL_NAME from config without importing at module level."""
    from tutor.config import MODEL_NAME
    return MODEL_NAME


def retrieve_node(state: dict, config: RunnableConfig, output_dir=None) -> dict:
    """
    LangGraph node: query Chroma with the (rewritten) user_question, populate
    retrieved_chunks.

    Reads:  state['user_question'], state['chapter_id']
    Writes: state['retrieved_chunks'], state['retrieval_status']

    P3.7 graceful low-context:
      - retrieval_status ∈ {"ok", "empty", "error"} drives the note the answer
        node injects (see prompts.build_context_block).
      - Each chunk is tagged "strong"/"weak" by whether its distance beats
        CONFIDENCE_THRESHOLD, so downstream code and the UI can tell well-
        grounded chunks from loose matches.
    """
    question = state.get("search_query") or state.get("user_question", "")
    if not question:
        logger.warning("retrieve_node: no user_question, returning empty chunks")
        return {"retrieved_chunks": [], "retrieval_status": "empty"}

    try:
        chapter_id = state.get("chapter_id")  # Phase 5: chapter routing
        chunks = retrieve(query=question, chapter_id=chapter_id, k=TOP_K, output_dir=output_dir)
        logger.debug(f"retrieve_node: {len(chunks)} chunks for query {question!r}")
        for c in chunks:
            c["confidence_tag"] = (
                "strong" if c.get("distance", 1.0) <= CONFIDENCE_THRESHOLD else "weak"
            )
        return {"retrieved_chunks": chunks, "retrieval_status": "ok" if chunks else "empty"}
    except IndexNotBuiltError as exc:
        # Fail gracefully: answer without context rather than crashing the graph.
        # The generate_answer_node checks for empty retrieved_chunks and adjusts
        # its prompt accordingly.
        logger.error(f"retrieve_node: index not built — {exc}")
        return {"retrieved_chunks": [], "retrieval_status": "error"}
    except Exception as exc:
        logger.error(f"retrieve_node: unexpected error — {exc}")
        return {"retrieved_chunks": [], "retrieval_status": "error"}