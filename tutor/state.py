"""
state.py

Defines ChatState, the shared state object every node in the tutor
graph reads from and writes to.

REDUCER SEMANTICS — read this before adding new fields.

LangGraph merges a node's returned dict into the overall state one
field at a time. By default that merge is "replace": whatever a node
returns for a key overwrites whatever was there before. `messages` is
the one exception here, explicitly opted into "append" semantics via
the `add_messages` reducer (Annotated[list[BaseMessage], add_messages]).

This split was a deliberate decision, not an oversight:

- `messages` MUST append. It's the actual conversation transcript,
  persisted by the checkpointer across every turn. Every user
  question and every answer needs to stay in it, turn after turn.
  (Future summarization, if/when it's added, changes what gets kept
  IN messages — it doesn't change messages from append to something
  else.)

- `retrieved_chunks`, `retrieved_images`, `user_question`, `answer`
  are deliberately plain "replace" fields. Each one is scratch space
  for the CURRENT turn only — e.g. Retrieve produces retrieved_chunks,
  Build Context reads it, Generate Answer reads the context and
  produces answer. Once a turn finishes, nothing — not later nodes in
  that same turn, not any future turn — ever needs that turn's
  retrieved_chunks again. The next question triggers a fresh retrieval
  for a (presumably) different question. If these accumulated instead
  of replacing, every turn would pile its retrieval results onto every
  previous turn's, forever — bloating context with irrelevant material
  from unrelated earlier questions. Plain replace is the correct
  default here, not a placeholder waiting to be upgraded to append.

  This remains correct even once parallel retrieval nodes exist
  (Phase 4: "Retrieve Text" + "Retrieve Image" both running in the same
  step) AS LONG AS text and images stay in separate fields, which they
  do here (retrieved_chunks vs retrieved_images). Two nodes writing to
  two different keys in the same step never contend with each other —
  replace-per-field is fine. The only case that would need a different
  reducer is two parallel nodes both writing the SAME key in the same
  step, which this schema doesn't do anywhere.

- `thread_id` and `lecture_title` are also plain replace, but in
  practice are set once per thread and never change for the life of
  that thread — replace vs append is moot for them, plain replace is
  just the simpler default.
"""

from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class ChatState(TypedDict):
    thread_id: str
    messages: Annotated[list[BaseMessage], add_messages]
    lecture_title: str
    chapter_id: int | None
    context_messages: list[BaseMessage]

    # ── Phase 6: tool calling ────────────────────────────────────────────
    is_command: bool                # set by detect_chapter when user asks for quiz/summary/flashcards
    command_type: str              # "quiz", "summary", or "flashcards"
    
    # ── Quiz mode (still used by the existing quiz loop) ─────────────────
    quiz_active: bool
    quiz_awaiting_answer: bool
    quiz_chapter_id: int | None
    quiz_questions: list[dict]
    quiz_answers: list[dict]
    quiz_index: int
    quiz_score: int
    quiz_total: int

    # ── Current-turn scratch space ───────────────────────────────────────
    user_question: str
    retrieved_chunks: list
    retrieved_images: list
    answer: str