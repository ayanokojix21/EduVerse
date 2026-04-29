"""
app/agents/schemas/quiz.py
───────────────────────────
Pydantic v2 boundary contracts for the Quiz Swarm nodes.

Node responsibility map:
  drafter_worker_node  → QuizQuestion      (structured schema, no tool call)
  reviewer_node        → FinalizeQuiz      (tool call to approve and format)
                       → TransferToDrafter (tool call to reject and redraft)
"""
from __future__ import annotations

from typing import Annotated, Literal
from typing_extensions import TypedDict

from pydantic import BaseModel, ConfigDict, Field, field_validator
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage

from app.agents.state import AgentState, merge_or_reset

class QuizState(AgentState):
    """Shared internal state with Parallel Reducer."""
    quiz_current_draft: Annotated[list[dict], merge_or_reset]


# ── Drafter Output ────────────────────────────────────────────────────────────

class QuizQuestion(BaseModel):
    """
    Single MCQ produced by one parallel Drafter Worker.
    Includes psychometric metadata for quality gating.
    """

    question: str = Field(
        description="The stem of the multiple-choice question. Should test depth, not recall.",
        min_length=10,
    )
    options: list[str] = Field(
        description="Exactly 4 answer choices (A–D). One correct, three misconception-based distractors.",
        min_length=4,
        max_length=4,
    )
    correct_answer: str = Field(
        description="The exact text of the correct option from the 'options' list.",
    )
    distractor_reasoning: str = Field(
        description=(
            "Explains WHY each distractor is wrong and which common misconception it targets: "
            "'Almost Correct', 'Inverse Logic', or 'Keyword Trap'."
        ),
    )
    bloom_level: Literal["Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"] = Field(
        description="Bloom's Taxonomy level this question targets.",
    )

    @field_validator("correct_answer")
    @classmethod
    def correct_answer_must_be_in_options(cls, v: str, info) -> str:
        options = info.data.get("options", [])
        if options and v not in options:
            raise ValueError(f"correct_answer '{v}' must be one of the provided options.")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "question": "What does F=ma represent?",
                    "options": ["Force = mass × acceleration", "Force = mass + acceleration", "Force = mass ÷ area", "Force = momentum × time"],
                    "correct_answer": "Force = mass × acceleration",
                    "distractor_reasoning": "Option B uses addition (inverse logic). Option C confuses with pressure formula (keyword trap). Option D confuses impulse with force (almost correct).",
                    "bloom_level": "Understand",
                }
            ]
        }
    )


# ── Reviewer: Rejection ───────────────────────────────────────────────────────

class TransferToDrafter(BaseModel):
    """
    Tool called by the Reviewer to reject the quiz set and trigger a redraft.
    Critique must be specific enough for the Drafter to correct the exact issue.
    """

    critique: str = Field(
        description=(
            "Actionable rejection reason: which question failed, why, and what the distractor "
            "issue is (e.g., 'Q2: correct answer is also technically valid for Distractor B')."
        ),
        min_length=15,
    )

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"critique": "Q1: distractor B is factually correct for relativistic scenarios. Needs a more specific qualifier."}]}
    )


# ── Reviewer: Approval ────────────────────────────────────────────────────────

class FinalizeQuiz(BaseModel):
    """
    Tool called by the Reviewer to approve the quiz set for student delivery.
    The 'note' field provides a brief quality summary for RL logging.
    """

    note: str = Field(
        description="Brief approval note confirming psychometric quality (e.g., 'All 3 questions passed unambiguity and distractor checks.').",
    )

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"note": "All 3 questions passed unambiguity and distractor checks."}]}
    )


# ── Swarm Boundaries (LangGraph) ──────────────────────────────────────────────

class QuizInputState(TypedDict, total=False):
    """Input boundary for the Quiz Swarm."""
    messages: Annotated[list[AnyMessage], add_messages]
    original_query: str
    difficulty: str
    user_id: str
    course_id: str

class QuizOutputState(TypedDict, total=False):
    """Standardized output for the Quiz Swarm."""
    messages: Annotated[list[AnyMessage], add_messages]
    response_text: str
    quiz_current_draft: list[dict]

class QuestionDrafterState(TypedDict):
    """Internal parallel payload for high-fidelity MCQ generation."""
    messages: list[AnyMessage]
    context_docs: list[dict]
    difficulty: str
    source_type: str
    index: int
    image_data: str | None
    image_mimetype: str | None

# Required: `from __future__ import annotations` defers Literal type evaluation.
# model_rebuild() forces Pydantic v2 to load them at import time.
QuizQuestion.model_rebuild()
TransferToDrafter.model_rebuild()
FinalizeQuiz.model_rebuild()
