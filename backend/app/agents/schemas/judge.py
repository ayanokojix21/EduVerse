from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field

class JudgeOutput(BaseModel):
    """
    Structured evaluation from the Teacher-as-a-Judge.
    Used for side-by-side (A/B) model comparison during Quality Gates.
    """
    score_a: float = Field(description="Score for Response A (historical/base model) from 1-10.")
    score_b: float = Field(description="Score for Response B (fine-tuned/new model) from 1-10.")
    winner: Literal["A", "B", "Tie"] = Field(description="The superior response according to the pedagogical rubric.")
    reasoning: str = Field(description="Detailed pedagogical justification for the scores.")
