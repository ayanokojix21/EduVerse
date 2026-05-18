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


# ── Swarm Boundaries (LangGraph) ──────────────────────────────────────────────

class RAGInputState(TypedDict, total=False):
    """Strict input boundaries from the orchestrator."""
    messages: Annotated[list[AnyMessage], add_messages]
    original_query: str
    difficulty: str
    user_id: str
    course_id: str
    quiz_topic_source: str
    image_data: str | None
    image_mimetype: str | None
    is_multimodal: bool

class RAGOutputState(TypedDict, total=False):
    """
    Strict output boundary for the RAG swarm.
    
    Every field here is consumed by either:
      - chat_service.py  (SSE retrieval_label event, explainability panel)
      - parent AgentState (HITL flag, critic grounding check)
    
    Fields NOT listed here are silently dropped by LangGraph at the
    subgraph boundary, even if nodes wrote them to state.
    """
    # Core response
    messages:               Annotated[list[AnyMessage], add_messages]
    response_text:          str
    citations:              list[Citation]
    context_docs:           list[dict]
    # Retrieval observability — read by chat_service SSE 'retrieval_label' event
    retrieval_label:        str
    top_reranker_score:     float
    explainability:         dict
    retrieval_ms:           int
    # HITL flag — set by hitl_node, read by generator_node and validator_node
    tutor_web_search_approved: bool
    # DPO training data
    dpo_pairs:              list[dict]
    tutor_raw_responses:    list[str]

# Required: `from __future__ import annotations` defers type evaluation.
# model_rebuild() forces Pydantic v2 to load them at import time.
PlannerOutput.model_rebuild()
TransferToValidator.model_rebuild()
TransferToGenerator.model_rebuild()
TransferToFormatter.model_rebuild()
