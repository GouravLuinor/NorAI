"""
cli.py

Minimal command-line chat loop for exercising the Phase 1/2 tutor
graph directly — not a production interface, just a way to actually
run the graph turn-by-turn and watch memory persist (and stay
isolated per thread) rather than trusting it on paper.

Usage:
    python -m tutor.cli

Commands inside the loop:
    /thread <id>   switch to a different conversation thread
                   (creates it if it doesn't exist yet)
    /history       print the full message history for the current thread
    /quit          exit

Anything else is sent to the tutor as a question.
"""

from langchain_core.messages import AIMessage, HumanMessage

from tutor.config import CHECKPOINT_DB_PATH, logger
from tutor.graph import build_graph
from tutor.memory import get_checkpointer


def _make_config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def run_cli():
    print("NorAI Tutor — Phase 1/2 CLI")
    print(f"Checkpoint DB: {CHECKPOINT_DB_PATH}")
    print("Commands: /thread <id>   /history   /quit")
    print()

    lecture_title = input(
        "Lecture title for this session (used for new threads): "
    ).strip() or "Untitled Lecture"

    thread_id = input("Starting thread_id (e.g. 'conv-a'): ").strip() or "default"

    with get_checkpointer() as checkpointer:
        graph = build_graph(checkpointer)

        print(f"\nOn thread '{thread_id}'. Ask a question, or use a /command.\n")

        while True:
            try:
                user_input = input(f"\n[{thread_id}] You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting.")
                break

            if not user_input:
                continue

            if user_input == "/quit":
                print("Exiting.")
                break

            if user_input.startswith("/thread "):
                thread_id = user_input.removeprefix("/thread ").strip()
                print(f"Switched to thread '{thread_id}'.\n")
                continue

            if user_input == "/history":
                config = _make_config(thread_id)
                snapshot = graph.get_state(config)
                messages = snapshot.values.get("messages", []) if snapshot.values else []
                if not messages:
                    print("(no history yet on this thread)\n")
                else:
                    for msg in messages:
                        role = "You" if isinstance(msg, HumanMessage) else "Tutor"
                        print(f"  {role}: {msg.content}")
                    print()
                continue

            config = _make_config(thread_id)

            # On a brand-new thread, ChatState has no lecture_title yet —
            # checking get_state lets us seed it once rather than
            # re-passing it (and risking overwriting it) on every turn.
            snapshot = graph.get_state(config)
            is_new_thread = not snapshot.values

            input_state = {
                "thread_id": thread_id,
                "user_question": user_input,
            }
            if is_new_thread:
                input_state["lecture_title"] = lecture_title

            try:
                result = graph.invoke(input_state, config)
            except Exception as e:
                logger.error(f"Graph invocation failed: {e}")
                print(f"(error: {e})\n")
                continue

            print(f"[{thread_id}] Tutor: {result['answer']}\n")


if __name__ == "__main__":
    run_cli()