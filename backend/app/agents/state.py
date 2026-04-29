"""
app/agents/state.py
────────────────────
Core LangGraph state definitions for the EduVerse Multi-Agent System.
"""
from __future__ import annotations

import operator
from typing import Annotated, Literal, Optional
from typing_extensions import TypedDict 
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

def merge_or_reset(existing: list, new: list) -> list:
    """Custom reducer for parallel state fields (Map-Reduce)."""
    if new and new[0] is None:
        return []
    return existing + (new or [])


# ── Reusable semantic types ───────────────────────────────────────────────────

TaskType = Literal["rag", "quiz", "feedback"]
DifficultyLevel = Literal["easy", "medium", "hard"]
RetrievalLabel = Literal[
    "CLASSROOM_GROUNDED",
    "CLASSROOM_LOW_CONFIDENCE",
    "CLASSROOM_INSUFFICIENT",
]
TopicSource = Literal["course_material", "weak_topics", "pyqs"]
RootCauseType = Literal[
    "Calculation Error",
    "Conceptual Gap",
    "Reading Misinterpretation",
    "Correct",
]


# ── Citation ────────────────────────────────────────────────────────────────

class Citation(BaseModel):
    """
    Grounded citation reference produced by the RAG Formatter.

    This model acts as a strict data boundary: any citation object stored
    in AgentState.citations MUST be constructed through this model, ensuring
    all downstream consumers (frontend, streaming API) receive valid data.
    """

    model_config = ConfigDict(
        validate_assignment=True,   
        extra="forbid",
        frozen=False,
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                {
                    "source_index": 1,
                    "title": "Newton's Laws of Motion - Chapter 3",
                    "alternate_link": "https://classroom.google.com/c/xyz/m/abc",
                    "file_url": "https://drive.google.com/file/d/xyz/view",
                    "content_type": "classroom_material",
                    "page_number": 42,
                    "snippet": "The second law states that F = ma, where F is net force...",
                }
            ]
        },
    )

    source_index: Annotated[
        int,
        Field(ge=1, description="1-indexed reference number used in the response text (e.g., [Doc 1])."),
    ]
    title: Annotated[
        str,
        Field(min_length=1, description="Human-readable title of the source material."),
    ]
    alternate_link: Annotated[
        str,
        Field(default="#", description="URL to the material's details page in Google Classroom or Drive."),
    ]
    file_url: Annotated[
        str | None,
        Field(default=None, description="Direct file URL required for page-precise PDF deep-linking."),
    ]
    content_type: Annotated[
        str,
        Field(default="classroom_material", description="Content origin tag for frontend routing."),
    ]
    page_number: Annotated[
        int | None,
        Field(default=None, ge=1, description="Exact 1-indexed page number for PDF deep-links."),
    ]
    snippet: Annotated[
        str,
        Field(min_length=5, description="Brief verbatim text snippet to help the student locate the source."),
    ]


# Required because `from __future__ import annotations` (PEP 563) defers all
# annotation evaluation to strings. Pydantic v2 needs model_rebuild() to force
# resolution of `Annotated[...]` type hints after the class is fully loaded.
Citation.model_rebuild()


# ── AgentState (TypedDict Backbone — Optimal for LangGraph) ──────────────────

class AgentState(TypedDict):
    """The single source of truth for the EduVerse MAS graph runtime."""

    # ── Conversation Context ──────────────────────────────────────────────────
    messages: Annotated[list[BaseMessage], add_messages]
    """LangGraph-managed message history with append reducer."""
    user_id: str
    """Authenticated User's unique identifier (from Google OAuth)."""
    course_id: str
    """The Google Classroom course in context for this session."""
    session_id: str
    """Unique streaming session ID for tracing and logging."""

    # ── Adaptive Learning ─────────────────────────────────────────────────────
    weak_topics: list[str]
    """Topics identified from prior sessions where the student struggles."""

    # ── Orchestration (Supervisor Output) ────────────────────────────────────
    original_query: str
    """The raw, unmodified query submitted by the student."""
    rewritten_queries: list[str]
    """Retrieval-optimized reformulation(s) produced by the Planner node."""
    needs_rewrite: bool
    """Flag controlling whether the Planner node should execute."""
    task: TaskType
    """Routing target determined by the Orchestrator."""
    difficulty: DifficultyLevel
    """Bloom's taxonomy difficulty level for content generation."""

    # ── Retrieval (RAG Executor Output) ──────────────────────────────────────
    context_docs: list[dict]
    """Raw document chunks returned by the hybrid retriever."""
    retrieval_label: RetrievalLabel
    """Grounding confidence label derived from the top reranker score."""
    top_reranker_score: float
    """The highest reranker relevance score for the retrieved chunk set."""
    retrieval_ms: int
    """Retrieval latency in milliseconds for performance observability."""
    explainability: dict
    """Debug metadata: scores, chunk counts, and retrieval strategy used."""

    # ── Multimodal Inputs ───────────────────────────────────────────────────
    image_data: Optional[str]
    """Base64 encoded image string."""
    image_mimetype: Optional[str]
    """Mimetype of the image (e.g., image/png)."""
    is_multimodal: bool
    """Flag to skip non-vision LLMs."""

    # ── RAG Tutor Swarm ───────────────────────────────────────────────────────
    tutor_current_draft: str
    """Working pedagogical response being refined by the Generator."""
    tutor_verified_draft: str
    """Generator draft that has been approved via TransferToFormatter."""
    tutor_revisions: int
    """Number of Generator→Validator revision loops completed."""
    tutor_reviewer_feedback: str
    """Critique from the Validator returned to the Generator for revision."""
    tutor_web_search_approved: bool
    """HITL permission flag for the Validator to use web_search_tool."""
    tutor_rejected_draft: str
    """Temporary storage for a rejected RAG generator draft (DPO mapping)."""
    tutor_raw_responses: Annotated[list[str], merge_or_reset]
    """Raw AIMessage contents (including <|thought|>) for DPO trajectory extraction."""

    # ── Quiz Swarm ────────────────────────────────────────────────────────────
    quiz_current_draft: Annotated[list[dict], merge_or_reset]
    """Parallel MCQ candidates produced by all Drafter Workers (Map step)."""
    quiz_revisions: int
    """Number of Reviewer→Drafter rejection loops completed."""
    quiz_reviewer_feedback: str
    """Critique from the Reviewer sent to the Drafter for regeneration."""
    quiz_best_draft: list[dict]
    """Best approved quiz set, stored for RL comparison."""
    quiz_best_score: int
    """Psychometric quality score of the best draft (for RL reward tracking)."""
    quiz_topic_source: TopicSource
    """Material source strategy selected by the Orchestrator."""
    quiz_rejected_draft: list[dict]
    """Temporary storage for a rejected Quiz Review draft (DPO mapping)."""
    quiz_raw_responses: Annotated[list[str], merge_or_reset]
    """Raw AIMessage contents (including <|thought|>) for DPO trajectory extraction."""

    # ── Feedback Swarm ────────────────────────────────────────────────────────
    quiz_responses: list[dict]
    """Student's submitted answers, keyed by question_text."""
    current_feedback_draft: dict
    """Working TransferToMentor payload being refined across Swarm iterations."""
    final_feedback: dict
    """Approved FinalizeFeedback payload ready for student delivery."""
    identified_weak_topics: list[str]
    """Topics flagged for remediation by the Diagnostician node."""
    feedback_revisions: int
    """Number of Mentor→Diagnostician rejection loops completed."""
    feedback_best_draft: dict
    """Best feedback draft stored for RL comparison."""
    feedback_best_score: int
    """Quality score of the best feedback draft (for RL reward tracking)."""
    feedback_rejected_draft: dict
    """Temporary storage for a rejected RCA Mentor evaluation (DPO mapping)."""
    feedback_raw_responses: Annotated[list[str], merge_or_reset]
    """Raw AIMessage contents (including <|thought|>) for DPO trajectory extraction."""
    safety_raw_responses: Annotated[list[str], merge_or_reset]
    """Raw reasoning traces from the Guardrails sentinel (Safety, Integrity, Output Shield)."""

    # ── Final Response (Formatter/Synthesizer Output) ─────────────────────────
    response_text: str
    """The final, student-facing markdown response string."""
    citations: list[Citation]
    """Grounded citation objects validated through the Citation schema."""
    consensus_reasoning: str
    """Optional CoT summary captured from agent_thoughts for LangSmith."""
    retry_count: int
    """Global retry count for error recovery at the graph level."""

    # ── Quality Gate (Critic) ─────────────────────────────────────────────────
    critic_review: dict
    """Structured CriticOutput dict stored for downstream graph routing."""
    critic_feedback: Annotated[list[str], operator.add]
    """Append-only issues list from the Critic for multi-turn retry prompting."""

    # ── Observability ─────────────────────────────────────────────────────────
    agent_thoughts: Annotated[list[dict], operator.add]
    """Append-only log of per-node reasoning traces (for LangSmith + RL)."""
    trace_url: str
    """LangSmith trace URL injected post-run for frontend debugging panels."""
    parallel_count: int
    """Number of parallel Drafter Workers launched (Quiz Map-Reduce control)."""
    
    # ── Offline Reinforcement Learning (DPO) ──────────────────────────────────
    dpo_pairs: Annotated[list[dict], operator.add]
    """Append-only global array capturing distinct (Prompt, Chosen, Rejected) pairs for specific agents."""


# ── TypeAdapter (External Boundary Validator) ─────────────────────────────────
_agent_state_validator: TypeAdapter[AgentState] | None = None


def get_state_validator() -> TypeAdapter[AgentState]:
    """
    Returns the singleton TypeAdapter for AgentState.
    Use at the API boundary (streaming endpoint) to validate the initial payload.

    Example::

        validator = get_state_validator()
        clean_state = validator.validate_python(raw_input_dict)
    """
    global _agent_state_validator
    if _agent_state_validator is None:
        _agent_state_validator = TypeAdapter(AgentState)
    return _agent_state_validator
