"""
app/agents/schemas/orchestrator.py
───────────────────────────────────
Pydantic v2 boundary contracts for the Orchestrator node.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class OrchestratorOutput(BaseModel):
    """
    Structured routing output from the Orchestrator.
    Determines which swarm handles the student's request.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"task": "quiz", "difficulty": "medium", "topic_source": "course_material"}
            ]
        }
    )

    task: Literal["rag", "quiz", "feedback"] = Field(
        description="Target swarm that handles this student request.",
    )
    difficulty: Literal["easy", "medium", "hard"] = Field(
        description="Bloom's difficulty level for the session.",
    )
    topic_source: Literal["course_material", "weak_topics", "pyqs"] = Field(
        default="course_material",
        description="Material source strategy for retrieval.",
    )


# Required: `from __future__ import annotations` defers annotation evaluation.
# Pydantic v2 needs model_rebuild() to resolve Literal type hints properly.
OrchestratorOutput.model_rebuild()
