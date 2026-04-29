from __future__ import annotations

from pydantic import BaseModel, Field

class RubricScores(BaseModel):
    grounding: float = Field(description="Factual accuracy and source grounding (0-1).")
    clarity: float = Field(description="Clarity and readability for the target student level (0-1).")
    pedagogy: float = Field(description="Adherence to Socratic/Feynman techniques (0-1).")
    cognitive_load: float = Field(description="Appropriateness of complexity (0-1).")

class TeacherAuditOutput(BaseModel):
    """
    Structured output from the Gemini Teacher during DPO distillation.
    """
    rubric_scores: RubricScores
    critique: str = Field(description="Detailed pedagogical critique of the student agent's response.")
    gold_standard_response: str = Field(description="The perfect, corrected, and highly Socratic response to be used as 'chosen' in DPO.")
    debiasing_notes: str = Field(description="Notes on how the response was sanitized for neutrality and bias.")
