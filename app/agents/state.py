"""
LangGraph agent state definitions.

``AgentState`` is the shared state dictionary that flows through every
node in the 7-node graph.  All fields are optional at entry (the graph
populates them progressively), except ``user_id``, ``course_id``,
``session_id``, and ``original_query`` which are set by the chat endpoint
before the graph runs.

``TutorDraft`` is the per-tutor output accumulator.  The ``operator.add``
reducer on ``tutor_drafts`` safely merges the outputs of the two parallel
tutor nodes into a single list — LangGraph's Send API guarantees that
both are appended before the synthesizer fan-in step runs.
"""
from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


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

    * **Supervisor** → ``task``, ``difficulty``
    * **Query Rewriter** → ``rewritten_queries``
    * **RAG Agent** → ``context_docs``, ``retrieval_label``,
      ``top_reranker_score``, ``retrieval_ms``, ``explainability``
    * **Tutor A / B** (parallel) → ``tutor_drafts`` (accumulates both)
    * **Synthesizer** → ``response_text``, ``citations``
    * **Critic** → ``critic_review``, ``critic_feedback``, ``retry_count``
    """

    # ── Conversation context ─────────────────────────────────────────────────
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: str
    course_id: str
    session_id: str

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
    # operator.add causes LangGraph to merge both parallel outputs into one list.
    tutor_drafts: Annotated[list[TutorDraft], operator.add]

    # ── Final answer (Synthesizer) ───────────────────────────────────────────
    response_text: str
    citations: list[dict]
    retry_count: int

    # ── Quality gate (Critic) ────────────────────────────────────────────────
    critic_review: dict
    critic_feedback: list[str]   # actionable issues; cleared after synthesis retry

    # ── Observability ────────────────────────────────────────────────────────
    agent_thoughts: Annotated[list[dict], operator.add]
    trace_url: str
