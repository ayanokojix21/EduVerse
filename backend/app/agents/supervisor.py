"""
Node 1 — Supervisor
Classifies the incoming student query into a specific task and difficulty constraint.
"""
from __future__ import annotations

import logging

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langsmith import traceable
from pydantic import BaseModel, Field

from app.agents.state import AgentState
from app.config import get_settings
from app.utils.llm_pool import RoundRobinLLM

logger = logging.getLogger(__name__)
settings = get_settings()


# ── Structured output schema ─────────────────────────────────────────────────

class SupervisorOutput(BaseModel):
    """Schema the supervisor LLM must conform to."""
    task: str = Field(
        description="One of: qa, explain, quiz, feedback, timetable",
        pattern="^(qa|explain|quiz|feedback|timetable)$",
    )
    difficulty: str = Field(
        description="One of: easy, medium, hard",
        pattern="^(easy|medium|hard)$",
    )
    needs_rewrite: bool = Field(
        description="Set to true if the query is conversational, missing context from previous messages, contains pronouns like 'it' or 'that', or needs strict keyword extraction. Set to false if it's already a clean, standalone search query.",
        default=True,
    )


# ── Node ─────────────────────────────────────────────────────────────────────

@traceable(name="supervisor")
async def supervisor_node(state: AgentState, config: RunnableConfig) -> dict:
    """
    Classify the student's query and reset tutor_drafts for the new turn.
    """
    # Lazy init to prevent import-time hangs
    llm = RoundRobinLLM.for_role(
        "structured", 
        temperature=0, 
        schema=SupervisorOutput
    )
    query = state["original_query"]
    weak_topics: list[str] = state.get("weak_topics") or []

    weak_context = (
        f"Known weak areas for this student: {', '.join(weak_topics)}"
        if weak_topics
        else "No prior weak areas identified."
    )

    prompt = (
        "You are a routing agent for an AI tutoring system.\n"
        "Classify the student question below into exactly one task type and one difficulty.\n\n"
        "task options  : qa (factual question), explain (concept explanation), "
        "quiz (practice question), feedback (student writing/work review), "
        "timetable (schedule/email events)\n"
        "difficulty options: easy, medium, hard\n\n"
        f"{weak_context}\n\n"
        f"Student question: {query}\n\n"
        "Return ONLY the structured JSON matching the required schema."
    )

    try:
        result: SupervisorOutput = await llm.ainvoke(
            [HumanMessage(content=prompt)], config=config
        )
        task = result.task
        difficulty = result.difficulty
        needs_rewrite = result.needs_rewrite
    except Exception as exc:  # noqa: BLE001
        logger.warning("Supervisor LLM failed, using defaults: %s", exc)        
        task, difficulty, needs_rewrite = "qa", "medium", True

    logger.info(
        "Supervisor â†’ task=%s difficulty=%s needs_rewrite=%s weak_topics=%d",
        task, difficulty, needs_rewrite, len(weak_topics),
    )

    return {
        "task": task,
        "difficulty": difficulty,
        "needs_rewrite": needs_rewrite,
        "tutor_drafts": None,
        "agent_thoughts": [
            {
                "node": "supervisor",
                "summary": f"Task: {task} · Difficulty: {difficulty}",
                "data": {
                    "task": task,
                    "difficulty": difficulty,
                    "needs_rewrite": needs_rewrite,
                    "weak_topics": weak_topics,
                },
            }
        ],
    }
