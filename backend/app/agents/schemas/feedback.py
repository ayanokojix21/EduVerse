"""
app/agents/schemas/feedback.py
──────────────────────────────
Pydantic v2 boundary contracts for the Feedback Swarm nodes.

Node responsibility map:
  diagnostician_node → TransferToMentor       (tool call to hand RCA to Mentor)
  mentor_node        → FinalizeFeedback        (tool call to publish to student)
                     → TransferToDiagnostician (tool call to reject and re-run RCA)
"""
from __future__ import annotations

from typing import Annotated, Literal
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ── Sub-schema: Per-Question RCA ──────────────────────────────────────────────

class QuestionFeedback(BaseModel):
    """
    Root Cause Analysis (RCA) for a single quiz question.
    Produced by the Diagnostician and consumed by the Mentor.
    """

    question_text: str = Field(description="The original question text.")
    is_correct: bool = Field(description="Whether the student answered correctly.")
    user_answer: str = Field(description="The student's submitted answer.")
    correct_answer: str = Field(description="The objectively correct answer.")
    explanation: str = Field(
        description="A clear explanation of why the correct answer is right."
    )
    root_cause: Literal[
        "Calculation Error",
        "Conceptual Gap",
        "Reading Misinterpretation",
        "Correct",
    ] = Field(
        description="The specific RCA category. Use 'Correct' if the student answered correctly.",
    )
    improvement_tip: str = Field(
        description="A concrete, actionable next step for the student to address the root cause.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "question_text": "What is F=ma?",
                    "is_correct": False,
                    "user_answer": "Force = mass + acceleration",
                    "correct_answer": "Force = mass × acceleration",
                    "explanation": "Newton's Second Law states force equals mass multiplied by acceleration.",
                    "root_cause": "Conceptual Gap",
                    "improvement_tip": "Review Chapter 3 on Newton's Laws and re-attempt the practice problems.",
                }
            ]
        }
    )


# ── Sub-schema: Mentor Quality Score ─────────────────────────────────────────

class FeedbackScoring(BaseModel):
    """
    Holistic quality score for the Feedback Swarm output.
    Each dimension rated out of 10 by the Mentor.
    """

    personalization: int = Field(
        ge=1, le=10,
        description="How well the feedback is tailored to the specific RCA (1–10).",
    )
    pedagogical_tone: int = Field(
        ge=1, le=10,
        description="How well Growth Mindset language is applied (1–10).",
    )
    clarity: int = Field(
        ge=1, le=10,
        description="How easy it is for the student to understand and act on the feedback (1–10).",
    )

    @model_validator(mode="after")
    def check_minimum_quality(self) -> "FeedbackScoring":
        """Ensure at least one dimension is actionable (> 5)."""
        if max(self.personalization, self.pedagogical_tone, self.clarity) < 6:
            raise ValueError(
                "All scores are critically low. The feedback draft must be regenerated."
            )
        return self

# ── Diagnostician → Mentor ────────────────────────────────────────────────────

class TransferToMentor(BaseModel):
    """
    Tool called by the Diagnostician to submit structured RCA results
    to the Mentor for pedagogical tone review.
    """

    overall_summary: str = Field(
        description="A brief, analytical summary of the student's performance pattern.",
        min_length=10,
    )
    question_feedback: list[QuestionFeedback] = Field(
        description="A per-question RCA breakdown.",
        min_length=1,
    )
    detected_weak_topics: list[str] = Field(
        description="2–3 specific topic strings the student should revisit (e.g., 'Newton's Laws', 'Kinematics').",
        min_length=1,
        max_length=3,
    )


# ── Mentor → Diagnostician (Rejection) ───────────────────────────────────────

class TransferToDiagnostician(BaseModel):
    """
    Tool called by the Mentor to reject the current RCA and request a deeper analysis.
    Used when any quality score is < 8.
    """

    scoring: FeedbackScoring = Field(
        description="The quality scores that triggered the rejection."
    )
    critique: str = Field(
        description=(
            "Specific critique explaining what was too generic or unclear in the RCA, "
            "so the Diagnostician can produce a more targeted analysis."
        ),
        min_length=10,
    )


# ── Mentor → Formatter (Approval) ────────────────────────────────────────────

class FinalizeFeedback(BaseModel):
    """
    Tool called by the Mentor to approve the feedback and publish it to the student.
    All scores must be >= 8 to call this tool.
    """

    scoring: FeedbackScoring = Field(
        description="The final quality scores confirming the feedback is ready for delivery."
    )

    @model_validator(mode="after")
    def scores_must_pass_quality_gate(self) -> "FinalizeFeedback":
        s = self.scoring
        if min(s.personalization, s.pedagogical_tone, s.clarity) < 8:
            raise ValueError(
                "Cannot finalize feedback: all scores must be >= 8. "
                "Use TransferToDiagnostician to request a revision."
            )
        return self


# ── Swarm Boundaries (LangGraph) ──────────────────────────────────────────────

class FeedbackInputState(TypedDict, total=False):
    """Input boundary for the Feedback Swarm."""
    messages: Annotated[list[AnyMessage], add_messages]
    quiz_responses: list[dict]
    user_id: str
    course_id: str

class FeedbackOutputState(TypedDict, total=False):
    """Standardized output for the Feedback Swarm."""
    messages: Annotated[list[AnyMessage], add_messages]
    response_text: str
    identified_weak_topics: list[str]

# Required: `from __future__ import annotations` defers type evaluation.
# model_rebuild() forces Pydantic v2 to load them at import time.
QuestionFeedback.model_rebuild()
FeedbackScoring.model_rebuild()
TransferToMentor.model_rebuild()
TransferToDiagnostician.model_rebuild()
FinalizeFeedback.model_rebuild()
