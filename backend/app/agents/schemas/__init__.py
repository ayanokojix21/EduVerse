"""
app/agents/schemas/__init__.py
───────────────────────────────
Public re-export surface for the EduVerse Agent Schema Registry.

Usage (flat import):
    from app.agents.schemas import OrchestratorOutput, QuizQuestion, CriticOutput

Usage (domain import — preferred for clarity):
    from app.agents.schemas.quiz import QuizQuestion, FinalizeQuiz
"""
from app.agents.schemas.orchestrator import OrchestratorOutput
from app.agents.schemas.rag import (
    PlannerOutput,
    TransferToFormatter,
    TransferToGenerator,
    TransferToValidator,
)
from app.agents.schemas.quiz import FinalizeQuiz, QuizQuestion, TransferToDrafter
from app.agents.schemas.feedback import (
    FinalizeFeedback,
    FeedbackScoring,
    QuestionFeedback,
    TransferToDiagnostician,
    TransferToMentor,
)
from app.agents.schemas.critic import CriticOutput

__all__ = [
    # Orchestrator
    "OrchestratorOutput",
    # RAG
    "PlannerOutput",
    "TransferToValidator",
    "TransferToGenerator",
    "TransferToFormatter",
    # Quiz
    "QuizQuestion",
    "TransferToDrafter",
    "FinalizeQuiz",
    # Feedback
    "QuestionFeedback",
    "FeedbackScoring",
    "TransferToMentor",
    "TransferToDiagnostician",
    "FinalizeFeedback",
    # Critic
    "CriticOutput",
]
