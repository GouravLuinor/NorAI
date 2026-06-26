"""
graph.py (Phase 3)

Updated graph topology:

    START
      └─ load_memory
          └─ rewrite_query      ← Phase 3: rewrites user_question for retrieval
              └─ retrieve        ← Phase 3: fills retrieved_chunks from Chroma
                  └─ generate_answer
                      └─ save_memory
                          └─ END

Everything else (checkpointer wiring, config threading, state shape) is
unchanged from Phase 1/2.

Replace your existing tutor/graph.py with this file.
"""

from langgraph.graph import StateGraph, START, END

from tutor.state import ChatState
from tutor.nodes import load_memory_node, generate_answer_node, save_memory_node
from tutor.nodes_retrieval import rewrite_query_node, retrieve_node, retrieve_images_node


def build_graph(checkpointer):
    """
    Build and compile the NorAI tutor StateGraph.

    Args:
        checkpointer: A LangGraph checkpointer (SqliteSaver or compatible).
                      Passed in from memory.py's get_checkpointer() context manager.

    Returns:
        A compiled LangGraph ready for .invoke() / .stream().
    """
    builder = StateGraph(ChatState)

    # ── Nodes ──────────────────────────────────────────────────────────────────
    builder.add_node("load_memory", load_memory_node)
    builder.add_node("rewrite_query", rewrite_query_node)
    builder.add_node("retrieve_images", retrieve_images_node)
    builder.add_node("retrieve", retrieve_node)
    builder.add_node("generate_answer", generate_answer_node)
    builder.add_node("save_memory", save_memory_node)

    # ── Edges ──────────────────────────────────────────────────────────────────
    # ── Edges ──────────────────────────────────────────────────────────────────
    builder.add_edge(START, "load_memory")
    # retrieve_images uses the original natural-language question (better for
    # matching screenshot captions), so it runs BEFORE rewrite_query.
    builder.add_edge("load_memory", "retrieve_images")
    # retrieve uses the rewritten keyword-optimised query, so it runs AFTER.
    builder.add_edge("load_memory", "rewrite_query")
    builder.add_edge("rewrite_query", "retrieve")
    # Both branches converge on generate_answer.
    builder.add_edge("retrieve", "generate_answer")
    builder.add_edge("retrieve_images", "generate_answer")
    builder.add_edge("generate_answer", "save_memory")
    builder.add_edge("save_memory", END)

    return builder.compile(checkpointer=checkpointer)