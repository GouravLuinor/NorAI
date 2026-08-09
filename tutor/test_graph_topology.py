"""
test_graph_topology.py — Test for LangGraph topology in tutor/graph.py.

Asserts edge connections without LLM or Gemini API calls.
Run:
    venv/bin/python tutor/test_graph_topology.py
"""

import sys
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from langgraph.checkpoint.memory import MemorySaver
from tutor.graph import build_graph


def test_graph_topology():
    checkpointer = MemorySaver()
    app = build_graph(checkpointer=checkpointer)
    graph = app.get_graph()

    # Extract edge pairs: (source, target)
    edges = [(edge.source, edge.target) for edge in graph.edges]

    # Verify query rewrite fan-out to both study notes and screenshot image retrieval
    assert ("rewrite_query", "retrieve") in edges, "Missing edge: rewrite_query -> retrieve"
    assert ("rewrite_query", "retrieve_images") in edges, "Missing edge: rewrite_query -> retrieve_images"

    # Verify start_normal does NOT directly edge to retrieve_images (must go through rewrite_query)
    assert ("start_normal", "retrieve_images") not in edges, "Unexpected edge: start_normal -> retrieve_images"

    # Verify fan-in to generate_answer
    assert ("retrieve", "generate_answer") in edges, "Missing edge: retrieve -> generate_answer"
    assert ("retrieve_images", "generate_answer") in edges, "Missing edge: retrieve_images -> generate_answer"

    # P3.3: answer → citation verification → memory → END
    assert ("generate_answer", "verify_citations") in edges, "Missing edge: generate_answer -> verify_citations"
    assert ("verify_citations", "save_memory") in edges, "Missing edge: verify_citations -> save_memory"
    assert ("save_memory", "__end__") in edges, "Missing edge: save_memory -> END"

    print("PASS test_graph_topology")


if __name__ == "__main__":
    test_graph_topology()
    print("\nAll graph topology tests passed.")
