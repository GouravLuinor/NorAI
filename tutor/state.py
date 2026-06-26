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

    # Identity — which conversation this is. Used as the checkpointer's
    # thread_id key, so memory for "Conversation A" never bleeds into
    # "Conversation B" even though both share the same SQLite file.
    thread_id: str

    # The full conversation transcript. Append-only via add_messages.
    # HumanMessage for the student's turns, AIMessage for the tutor's.
    messages: Annotated[list[BaseMessage], add_messages]

    # Which lecture this thread is scoped to. Set once when the thread
    # is created; read by prompts.py to ground the tutor's system
    # prompt ("you are tutoring the student on {lecture_title}").
    lecture_title: str

    # --- Current-turn scratch space (plain replace — see module
    # docstring for why these are NOT add_messages-style accumulators) ---

    # The student's question for THIS turn, as raw text. Mirrors the
    # latest HumanMessage in `messages` but kept as a plain string too
    # since several Phase 3+ nodes (query rewrite, retrieval) want to
    # read/transform it without unpacking a BaseMessage each time.
    user_question: str

    # Phase 3+: chunks pulled from the knowledge base for this turn's
    # question. Empty list in Phase 1/2, where there's no retrieval yet.
    retrieved_chunks: list

    # Phase 4+: screenshot references retrieved for this turn's
    # question (see outputs/screenshots/keyframes metadata — path,
    # reason, section, importance). Empty list until Phase 4.
    retrieved_images: list

    # This turn's generated answer, as plain text. Also gets wrapped
    # into an AIMessage and appended to `messages` by generate_answer
    # node — kept as a separate plain-text field too since it's
    # convenient for the CLI harness (and later, any API layer) to
    # read the latest answer directly without unpacking messages.
    answer: str