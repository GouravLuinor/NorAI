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
"""

from __future__ import annotations
import re
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from .retriever import IndexNotBuiltError, retrieve, retrieve_images
from .retrieval_config import TOP_K, TOP_K_IMAGES
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
    (re.compile(r"\b(?:in|from)\s+the\s+(\w+)\s+chapter\b", re.IGNORECASE),
     lambda m: _WORD_TO_NUM.get(m.group(1).lower())),
]


def _extract_chapter_id(text: str) -> int | None:
    """Return chapter number if the text contains an explicit chapter reference."""
    for pattern, extractor in _CHAPTER_REGEXES:
        match = pattern.search(text)
        if match:
            num = extractor(match)
            if num is not None:
                return num
    return None


def detect_chapter_node(state: dict, config: RunnableConfig) -> dict:
    question = state.get("user_question", "")
    result = {
        "chapter_id": None,
        "is_command": False,
        "command_type": "",          # "quiz", "summary", or "flashcards"
    }

    chapter_id = _extract_chapter_id(question)
    if chapter_id is not None:
        result["chapter_id"] = chapter_id

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

def retrieve_images_node(state: dict, config: RunnableConfig) -> dict:
    """
    Retrieve relevant screenshots using the original user question.
    Uses a direct Chroma connection to avoid cache conflicts with
    parallel text retrieval.
    """
    import chromadb
    from tutor.retrieval_config import CHROMA_DIR, SCREENSHOT_COLLECTION_NAME, TOP_K_IMAGES
    from tutor.embedding import GeminiEmbeddingFunction
    
    query = state.get("user_question", "")
    
    retrieved_images: list = []
    try:
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        embedding_fn = GeminiEmbeddingFunction(role="query")
        collection = client.get_collection(
            name=SCREENSHOT_COLLECTION_NAME,
            embedding_function=embedding_fn,
        )
        chapter_id = state.get("chapter_id")  # Phase 5: chapter routing
        where_filter = None
        if chapter_id is not None:
            where_filter = {"chapter_id": chapter_id}

        results = collection.query(
            query_texts=[query],
            n_results=TOP_K_IMAGES,
            where=where_filter,
            include=["metadatas", "distances"],
        )
        
        if results["ids"] and results["ids"][0]:
            for idx in range(len(results["ids"][0])):
                meta = results["metadatas"][0][idx]
                dist = results["distances"][0][idx]
                retrieved_images.append({
                    "path": meta["path"],
                    "section": meta.get("section", ""),
                    "importance": meta.get("importance", 0),
                    "chapter_id": meta.get("chapter_id"),
                    "distance": dist,
                })
            retrieved_images.sort(key=lambda x: (x["distance"], -x["importance"]))
    except Exception:
        logger.error("[retrieve_images_node] Unexpected error:", exc_info=True)
    
    return {"retrieved_images": retrieved_images}

def rewrite_query_node(state: dict, config: RunnableConfig) -> dict:
    """
    LangGraph node: rewrite state['user_question'] into a retrieval-optimised query.

    Reads:  state['user_question'], state['messages'] (recent history)
    Writes: state['user_question'] (overwritten with the rewritten query)
            state['retrieved_chunks'] = []  (clear any stale chunks from prior turn)
    """
    question = state.get("user_question", "")
    if not question:
        logger.warning("rewrite_query_node: no user_question in state, skipping rewrite")
        return {"retrieved_chunks": []}

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

    rewrite_prompt = (
        f"Conversation so far:\n{history_str}\n\n"
        f"Student's latest question: {question}\n\n"
        f"Rewritten search query:"
    )

    # Use the LLM from config (same model as generate_answer_node, already
    # initialised there — but we construct it independently here so the node
    # is self-contained and testable in isolation)
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI  # type: ignore
        from tutor.config import get_api_key

        llm = ChatGoogleGenerativeAI(
            model=_get_model_from_config(),
            temperature=0.0,  # rewrite should be deterministic
            google_api_key=get_api_key(),
        )
    except Exception as exc:
        logger.warning(f"rewrite_query_node: LLM init failed ({exc}), using raw question")
        return {"user_question": question, "retrieved_chunks": []}

    try:
        response = llm.invoke(
            [SystemMessage(content=_REWRITE_SYSTEM), HumanMessage(content=rewrite_prompt)]
        )
        content = response.content
        if isinstance(content, list):
            text_blocks = [block["text"] for block in content if isinstance(block, dict) and "text" in block]
            content = "\n".join(text_blocks)
            
        rewritten = content.strip()

        if rewritten:
            logger.debug(f"Query rewrite: {question!r} → {rewritten!r}")
            return {"user_question": rewritten, "retrieved_chunks": []}
    except Exception as exc:
        logger.warning(f"rewrite_query_node: LLM call failed ({exc}), using raw question")

    return {"user_question": question, "retrieved_chunks": []}


def _get_model_from_config() -> str:
    """Fallback: read MODEL_NAME from config without importing at module level."""
    from tutor.config import MODEL_NAME
    return MODEL_NAME


def retrieve_node(state: dict, config: RunnableConfig) -> dict:
    """
    LangGraph node: query Chroma with the (rewritten) user_question, populate
    retrieved_chunks.

    Reads:  state['user_question'], state['lecture_title'] (unused for now,
            but available for chapter_id filtering in future)
    Writes: state['retrieved_chunks']

    Chapter filtering:
        Currently NOT filtering by chapter_id — we search the full index.
        Rationale: the user may ask cross-chapter questions, and we don't yet
        have a reliable way to infer which chapter they're asking about from the
        question alone. Add chapter_id filtering here once we have a routing
        signal (e.g. the user says "in chapter 3...").
    """
    question = state.get("user_question", "")
    if not question:
        logger.warning("retrieve_node: no user_question, returning empty chunks")
        return {"retrieved_chunks": []}

    try:
        chapter_id = state.get("chapter_id")  # Phase 5: chapter routing
        chunks = retrieve(query=question, chapter_id=chapter_id, k=TOP_K)
        logger.debug(f"retrieve_node: {len(chunks)} chunks for query {question!r}")
        return {"retrieved_chunks": chunks}
    except IndexNotBuiltError as exc:
        # Fail gracefully: answer without context rather than crashing the graph.
        # The generate_answer_node checks for empty retrieved_chunks and adjusts
        # its prompt accordingly.
        logger.error(f"retrieve_node: index not built — {exc}")
        return {"retrieved_chunks": []}
    except Exception as exc:
        logger.error(f"retrieve_node: unexpected error — {exc}")
        return {"retrieved_chunks": []}