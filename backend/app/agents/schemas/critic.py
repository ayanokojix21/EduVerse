"""
app/agents/schemas/critic.py
─────────────────────────────
Pydantic v2 boundary contract for the Global Critic quality gate.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CriticOutput(BaseModel):
    """
    Structured hallucination audit result from the Global Critic.

    Severity levels:
      - none: All claims are supported by sources.
      - low:  Claims made beyond sources but are common knowledge.
      - high: Direct contradiction of a source fact — blocks delivery.
    """

    severity: Literal["none", "low", "high"] = Field(
        description="Hallucination severity level.",
    )
    issues: list[str] = Field(
        default_factory=list,
        description=(
            "Specific, actionable issues. For severity='high', each item must name the exact "
            "claim and the conflicting source (e.g., 'Response says 1920, Doc 2 says 1914'). "
            "Empty list if severity is not 'high'."
        ),
    )
    passed: bool = Field(
        description=(
            "True if the response is acceptable for student delivery. "
            "Set to False ONLY on severity='high' (confirmed factual contradiction)."
        ),
    )
    required_facts: list[str] = Field(
        default_factory=list,
        description=(
            "Facts from sources that MUST be corrected in any revision. "
            "Only populated for severity='high'."
        ),
    )
    pedagogical_fidelity: Literal["poor", "average", "excellent"] = Field(
        default="average",
        description="Rating of how well the agent follows Socratic principles (not just correctness).",
    )
    is_socratic: bool = Field(
        default=True,
        description="True if the agent leads the student to the answer rather than giving it directly.",
    )
    validated_citations: int = Field(
        default=0,
        description="Number of unique, factually correct citations found in the response.",
    )

    @model_validator(mode="after")
    def validate_severity_consistency(self) -> "CriticOutput":
        """Enforce that issues and required_facts are only populated for high severity."""
        if self.severity != "high":
            if self.issues:
                self.issues = []
            if self.required_facts:
                self.required_facts = []
        if self.severity == "high" and self.passed:
            raise ValueError(
                "Inconsistent state: severity='high' requires passed=False. "
                "A confirmed hallucination cannot be marked as passed."
            )
        return self

# Required: `from __future__ import annotations` defers type evaluation.
# model_rebuild() forces Pydantic v2 to load them at import time.
CriticOutput.model_rebuild()
