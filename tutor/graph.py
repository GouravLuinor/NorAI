from langgraph.graph import StateGraph, START, END
from tutor.state import ChatState
from tutor.nodes import load_memory_node, generate_answer_node, save_memory_node
from tutor.nodes_retrieval import (
    rewrite_query_node, retrieve_node, retrieve_images_node, detect_chapter_node
)
from tutor.quiz_nodes import quiz_ask, quiz_store_answer, quiz_llm_evaluate
from tutor.commands import execute_command


def build_graph(checkpointer):
    builder = StateGraph(ChatState)

    # Nodes
    builder.add_node("load_memory", load_memory_node)
    builder.add_node("detect_chapter", detect_chapter_node)
    builder.add_node("rewrite_query", rewrite_query_node)
    builder.add_node("retrieve_images", retrieve_images_node)
    builder.add_node("retrieve", retrieve_node)
    builder.add_node("generate_answer", generate_answer_node)
    builder.add_node("save_memory", save_memory_node)
    builder.add_node("execute_command", execute_command)

    # Quiz nodes
    builder.add_node("quiz_ask", quiz_ask)
    builder.add_node("quiz_store_answer", quiz_store_answer)
    builder.add_node("quiz_llm_evaluate", quiz_llm_evaluate)
    builder.add_node("start_normal", lambda state, config: {})

    # Routing
    builder.add_edge(START, "load_memory")
    builder.add_edge("load_memory", "detect_chapter")

    def route_after_intent(state: dict) -> str:
        if state.get("quiz_active"):
            if state.get("quiz_awaiting_answer"):
                return "quiz_store_answer"
            idx = state.get("quiz_index", 0)
            total = state.get("quiz_total", 0)
            return "quiz_ask" if idx < total else "quiz_llm_evaluate"

        if state.get("is_command"):
            return "execute_command"
        return "start_normal"

    builder.add_conditional_edges(
        "detect_chapter",
        route_after_intent,
        {
            "execute_command": "execute_command",
            "quiz_store_answer": "quiz_store_answer",
            "quiz_ask": "quiz_ask",
            "quiz_llm_evaluate": "quiz_llm_evaluate",
            "start_normal": "start_normal",
        }
    )

    # Command executor -> quiz ask or save_memory
    def route_after_command(state: dict) -> str:
        if state.get("quiz_active"):
            return "quiz_ask"
        return "save_memory"

    builder.add_conditional_edges(
        "execute_command",
        route_after_command,
        {"quiz_ask": "quiz_ask", "save_memory": "save_memory"}
    )

    # Quiz internal edges
    builder.add_edge("quiz_ask", END)
    def route_after_store(state):
        idx = state.get("quiz_index", 0)
        total = state.get("quiz_total", 0)
        return "quiz_ask" if idx < total else "quiz_llm_evaluate"
    builder.add_conditional_edges("quiz_store_answer", route_after_store,
                                  {"quiz_ask": "quiz_ask", "quiz_llm_evaluate": "quiz_llm_evaluate"})
    builder.add_edge("quiz_llm_evaluate", "save_memory")

    # Normal Q&A flow
    builder.add_edge("start_normal", "retrieve_images")
    builder.add_edge("start_normal", "rewrite_query")
    builder.add_edge("rewrite_query", "retrieve")
    builder.add_edge("retrieve", "generate_answer")
    builder.add_edge("retrieve_images", "generate_answer")
    builder.add_edge("generate_answer", "save_memory")
    builder.add_edge("save_memory", END)

    return builder.compile(checkpointer=checkpointer)