"""
app/agents/schemas/rag.py
──────────────────────────
Pydantic v2 boundary contracts for the RAG Swarm nodes.

Node responsibility map:
  planner_node    → PlannerOutput          (structured schema, no tool call)
  generator_node  → TransferToValidator    (tool call to hand off draft)
  validator_node  → TransferToGenerator    (tool call to reject draft)
                 → TransferToFormatter    (tool call to approve draft)
"""
from __future__ import annotations

from typing import Annotated
from typing_extensions import TypedDict
from pydantic import BaseModel, ConfigDict, Field
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage
from app.agents.state import Citation


# ── Planner ───────────────────────────────────────────────────────────────────

class PlannerOutput(BaseModel):
    """
    Structured output for the Retrieval Planner.
    The LLM rewrites the student's query into a dense search string.
    """

    search_query: str = Field(
        description=(
            "Optimized, keyword-dense query for hybrid vector + BM25 retrieval. "
            "Technical terms should be fully expanded."
        ),
        min_length=5,
    )

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"search_query": "Newton's second law force mass acceleration F=ma"}]}
    )


# ── Generator → Validator ─────────────────────────────────────────────────────

class TransferToValidator(BaseModel):
    """
    Tool called by the Tutor Generator to submit its pedagogical draft
    for quality and grounding verification.
    """

    draft_answer: str = Field(
        description="The complete Socratic, Feynman-scaffolded response to be fact-checked.",
        min_length=20,
    )

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"draft_answer": "Imagine gravity like... [Doc 1]"}]}
    )


# ── Validator → Generator (Rejection) ────────────────────────────────────────

class TransferToGenerator(BaseModel):
    """
    Tool called by the Validator to reject a draft and request a revision.
    The feedback field must be specific and actionable.
    """

    feedback: str = Field(
        description=(
            "Precise critique of what is wrong. Must cite which claim is incorrect "
            "and reference the source that contradicts it (e.g., 'Doc 2 says X, draft says Y')."
        ),
        min_length=10,
    )

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"feedback": "Doc 2 states 1905, but draft says 1912."}]}
    )


# ── Validator → Formatter (Approval) ─────────────────────────────────────────

class TransferToFormatter(BaseModel):
    """
    Tool called by the Validator to approve a draft and send it to the
    Formatter for final structural rendering.
    """

    verified_answer: str = Field(
        description="The fully fact-checked and approved pedagogical response.",
        min_length=20,
    )

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"verified_answer": "Newton's 2nd Law states F=ma [Doc 1]..."}]}
    )


# ── Swarm Boundaries (LangGraph) ──────────────────────────────────────────────

class RAGInputState(TypedDict, total=False):
    """Strict input boundaries from the orchestrator."""
    messages: Annotated[list[AnyMessage], add_messages]
    original_query: str
    difficulty: str
    user_id: str
    course_id: str
    quiz_topic_source: str

class RAGOutputState(TypedDict, total=False):
    """Strict output boundaries for the swarm."""
    messages: Annotated[list[AnyMessage], add_messages]
    response_text: str
    citations: list[Citation]
    context_docs: list[dict]

# Required: `from __future__ import annotations` defers type evaluation.
# model_rebuild() forces Pydantic v2 to load them at import time.
PlannerOutput.model_rebuild()
TransferToValidator.model_rebuild()
TransferToGenerator.model_rebuild()
TransferToFormatter.model_rebuild()
