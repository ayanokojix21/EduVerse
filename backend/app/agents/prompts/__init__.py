"""
app/agents/prompts/__init__.py
───────────────────────────────
Public re-export surface for all EduVerse agent prompt templates.
"""
from app.agents.prompts.orchestrator import ORCHESTRATOR_PROMPT, ORCHESTRATOR_SYSTEM
from app.agents.prompts.rag import (
    PLANNER_PROMPT,
    GENERATOR_PROMPT,
    GENERATOR_SYSTEM,
    VALIDATOR_PROMPT,
    VALIDATOR_SYSTEM,
)
from app.agents.prompts.quiz import (
    DRAFTER_PROMPT,
    DRAFTER_SYSTEM,
    REVIEWER_PROMPT,
    REVIEWER_SYSTEM,
)
from app.agents.prompts.feedback import (
    DIAGNOSTICIAN_PROMPT,
    DIAGNOSTICIAN_SYSTEM,
    MENTOR_PROMPT,
    MENTOR_SYSTEM,
)
from app.agents.prompts.critic import CRITIC_SYSTEM_PROMPT
from app.agents.prompts.guardrails import (
    INPUT_MODERATOR_PROMPT,
    ACADEMIC_INTEGRITY_PROMPT,
    REFUSAL_PROMPT,
    OUTPUT_SHIELD_PROMPT,
)
from app.agents.prompts.teacher import TEACHER_PROMPT

__all__ = [
    # Orchestrator
    "ORCHESTRATOR_SYSTEM",
    "ORCHESTRATOR_PROMPT",
    # RAG
    "PLANNER_PROMPT",
    "GENERATOR_SYSTEM",
    "GENERATOR_PROMPT",
    "VALIDATOR_SYSTEM",
    "VALIDATOR_PROMPT",
    # Quiz
    "DRAFTER_SYSTEM",
    "DRAFTER_PROMPT",
    "REVIEWER_SYSTEM",
    "REVIEWER_PROMPT",
    # Feedback
    "DIAGNOSTICIAN_SYSTEM",
    "DIAGNOSTICIAN_PROMPT",
    "MENTOR_SYSTEM",
    "MENTOR_PROMPT",
    # Critic
    "CRITIC_SYSTEM_PROMPT",
    # Guardrails
    "INPUT_MODERATOR_PROMPT",
    "ACADEMIC_INTEGRITY_PROMPT",
    "REFUSAL_PROMPT",
    "OUTPUT_SHIELD_PROMPT",
    # Teacher
    "TEACHER_PROMPT",
]
