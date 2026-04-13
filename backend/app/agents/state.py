from __future__ import annotations

import operator
from typing import Annotated, TypedDict, Any

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


# ── Schemas ──────────────────────────────────────────────────────────────────

class Citation(BaseModel):
    """Grounded citation reference."""
    source_index: int = Field(description="1-indexed reference to the source index")
    title: str = Field(description="Title of the source material")
    alternate_link: str = Field(default="#", description="Link to the material details page (Classroom/Drive)")
    file_url: str | None = Field(default=None, description="Direct URL to the file attachment (required for page-precise deep-linking)")
    content_type: str = Field(default="classroom_material")
    page_number: int | None = Field(default=None, description="Exact page number in the source material")
    snippet: str = Field(description="Brief relevant text snippet helping the student find the fact")


class TutorDraft(BaseModel):
    """Output of a single parallel tutor agent node."""
    agent_id: str = Field(description="'tutor_a' or 'tutor_b'")
    style: str = Field(description="'concise' or 'explanatory'")
    response_text: str = Field(description="The actual tutoring response text")
    citations: list[Citation] = Field(default_factory=list)
    reasoning: str = Field(description="One-sentence pedagogical reasoning")


# ── Reducers ─────────────────────────────────────────────────────────────────

def _reset_or_add_drafts(
    existing: list[TutorDraft] | None,
    update: list[TutorDraft] | None | None,
) -> list[TutorDraft]:
    """Smart reducer for tutor_drafts (None = reset)."""
    if update is None:
        return []
    return list(existing or []) + list(update)


# ── State ────────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    """
    Full LangGraph shared state.
    Validated as a modern declarative schema.
    """

    # ── Conversation context ─────────────────────────────────────────────────
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: str
    course_id: str
    session_id: str

    # ── Adaptive learning context ────────────────────────────────────────────
    weak_topics: list[str]

    # ── Classification (Supervisor) ──────────────────────────────────────────
    original_query: str
    rewritten_queries: list[str]
    needs_rewrite: bool
    task: str        # "qa" | "explain" | "quiz" | "feedback" | "timetable"
    difficulty: str  # "easy" | "medium" | "hard"

    # ── Retrieval (RAG Agent) ────────────────────────────────────────────────
    context_docs: list[dict]
    retrieval_label: str    # "CLASSROOM_GROUNDED" | "CLASSROOM_LOW_CONFIDENCE" | "CLASSROOM_INSUFFICIENT"
    top_reranker_score: float
    retrieval_ms: int
    explainability: dict

    # ── Parallel tutor output ────────────────────────────────────────────────
    tutor_drafts: Annotated[list[TutorDraft], _reset_or_add_drafts]

    # ── Email & Calendar ─────────────────────────────────────────────────────
    email_events: list[dict]
    timetable: dict
    
    # ── Final answer (Synthesizer) ───────────────────────────────────────────
    response_text: str
    citations: list[Citation]
    consensus_reasoning: str
    retry_count: int

    # ── Quality gate (Critic) ────────────────────────────────────────────────
    critic_review: dict
    critic_feedback: list[str]

    # ── Observability ────────────────────────────────────────────────────────
    agent_thoughts: Annotated[list[dict], operator.add]
    trace_url: str
