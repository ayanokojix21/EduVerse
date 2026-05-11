"""
app/agents/schemas/guardrails.py
──────────────────────────────────
Pydantic v2 boundary contracts for the Guardrails Swarm.
"""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field, ConfigDict

class SafetyOutput(BaseModel):
    """Structured output for the Input Moderator."""
    decision: Literal["SAFE", "UNSAFE"] = Field(description="The safety verdict.")
    reason: str | None = Field(default=None, description="Detailed reason for UNSAFE verdict.")
    
    model_config = ConfigDict()

class IntegrityOutput(BaseModel):
    """Structured output for the Academic Integrity Auditor."""
    decision: Literal["Socratic", "Refusal"] = Field(description="Whether the query is pedagogically valid or cheating.")
    reason: str | None = Field(default=None, description="Reasoning for the refusal.")
    
    model_config = ConfigDict()

class OutputShieldOutput(BaseModel):
    """Structured output for the Output Moderator."""
    decision: Literal["APPROVED", "REDACTED"] = Field(description="The quality gate verdict.")
    reason: str | None = Field(default=None, description="Redaction reason (if REDACTED).")
    
    model_config = ConfigDict()

SafetyOutput.model_rebuild()
IntegrityOutput.model_rebuild()
OutputShieldOutput.model_rebuild()
