"""
LangGraph agent state definitions.

``AgentState`` is the shared state dictionary that flows through every
node in the 7-node graph.  All fields are optional at entry (the graph
populates them progressively), except ``user_id``, ``course_id``,
``session_id``, and ``original_query`` which are set by the chat endpoint
before the graph runs.

Reducers
--------
* ``add_messages`` on ``messages`` — standard LangChain accumulator; appends
  new messages rather than replacing.  The synthesizer node now also appends
  an AIMessage so the full conversation history (Q+A) is captured.

* ``operator.add`` on ``agent_thoughts`` — accumulates thoughts from all 7
  nodes into one ordered list for the UI Brain tab.

* ``_reset_or_add_drafts`` on ``tutor_drafts`` — custom reducer:
    - ``None``  → reset to [] (used by supervisor at start of each turn)
    - ``list``  → accumulate (used by parallel tutor nodes to fan-in)
  This fixes the historical bug where `operator.add` caused previous-turn
  drafts to accumulate, making the synthesizer see stale data.
"""
from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


def _reset_or_add_drafts(
    existing: list | None,
    update: list | None,
) -> list:
    """
    Smart reducer for ``tutor_drafts``.

    ``update=None``  → reset to [] (supervisor calls this at turn start)
    ``update=[...]`` → accumulate onto existing (parallel tutor fan-in)
    """
    if update is None:
        return []
    return list(existing or []) + list(update)


class TutorDraft(TypedDict):
    """Output of a single parallel tutor agent node."""

    agent_id: str       # "tutor_a" | "tutor_b"
    style: str          # "concise" | "explanatory"
    response_text: str
    citations: list[dict]
    reasoning: str


class AgentState(TypedDict):
    """
    Full LangGraph shared state.

    Fields populated at each pipeline stage:

    * **Supervisor** → ``task``, ``difficulty``; resets ``tutor_drafts``
    * **Query Rewriter** → ``rewritten_queries``
    * **RAG Agent** → ``context_docs``, ``retrieval_label``,
      ``top_reranker_score``, ``retrieval_ms``, ``explainability``
    * **Tutor A / B** (parallel) → ``tutor_drafts`` (accumulates both)
    * **Synthesizer** → ``response_text``, ``citations``, appends AIMessage
    * **Critic** → ``critic_review``, ``critic_feedback``, ``retry_count``
    """

    # ── Conversation context ─────────────────────────────────────────────────
    # add_messages: appends new BaseMessage objects, never overwrites history.
    # Both HumanMessages (from chat.py) and AIMessages (from synthesizer)
    # are stored here, giving agents a proper multi-turn conversation view.
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: str
    course_id: str
    session_id: str

    # ── Adaptive learning context (loaded from MongoDB before graph runs) ────
    # weak_topics are fetched by chat.py from ProfileStore and injected into
    # initial_state.  tutor agents use them to tailor explanations.
    weak_topics: list[str]

    # ── Classification (Supervisor) ──────────────────────────────────────────
    original_query: str
    rewritten_queries: list[str]
    task: str        # "qa" | "explain" | "quiz" | "feedback"
    difficulty: str  # "easy" | "medium" | "hard"

    # ── Retrieval (RAG Agent) ────────────────────────────────────────────────
    context_docs: list[dict]
    retrieval_label: str    # "CLASSROOM_GROUNDED" | "CLASSROOM_PARTIAL_WEB" | "WEB_ONLY"
    top_reranker_score: float
    retrieval_ms: int
    explainability: dict

    # ── Parallel tutor output ────────────────────────────────────────────────
    # Custom reducer: None = reset (supervisor), list = accumulate (tutors).
    tutor_drafts: Annotated[list[TutorDraft], _reset_or_add_drafts]

    # ── Email ────────────────────────────────────────────────
    email_events: list[dict]
    timetable: dict
    

    # ── Final answer (Synthesizer) ───────────────────────────────────────────
    response_text: str
    citations: list[dict]
    retry_count: int

    # ── Quality gate (Critic) ────────────────────────────────────────────────
    critic_review: dict
    critic_feedback: list[str]   # cleared after synthesis retry

    # ── Observability ────────────────────────────────────────────────────────
    # operator.add accumulates thoughts from every node.
    agent_thoughts: Annotated[list[dict], operator.add]
    trace_url: str
