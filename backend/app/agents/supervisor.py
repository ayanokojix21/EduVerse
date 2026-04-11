"""
Node 1 — Supervisor

Classifies the incoming student query into:
  * task       : "qa" | "explain" | "quiz" | "feedback"
  * difficulty : "easy" | "medium" | "hard"

Memory reset
------------
The supervisor also resets ``tutor_drafts`` to [] by returning ``None`` for
that field.  This is the mechanism used by the custom ``_reset_or_add_drafts``
reducer in state.py — returning ``None`` signals "start of new turn, discard
previous drafts."  Without this reset, the parallel tutor nodes would
accumulate across turns and the synthesizer would see stale drafts.

LangChain best-practices applied
----------------------------------
* ``with_structured_output`` — instructs the LLM to return a validated
  Pydantic model directly; eliminates manual json.loads() and error handling.
* ``RunnableConfig`` passed through so tracing config propagates.
"""
from __future__ import annotations

import logging

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_groq import ChatGroq
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


# ── LLM pool (round-robin across models with auto-fallback) ──────────────────
# Uses the structured pool: llama-3.3-70b → llama-4-scout → kimi-k2 → llama-3.1-8b

_supervisor_llm = RoundRobinLLM.for_role("structured", temperature=0).with_structured_output(
    SupervisorOutput
)


# ── Node ─────────────────────────────────────────────────────────────────────

@traceable(name="supervisor")
async def supervisor_node(state: AgentState, config: RunnableConfig) -> dict:
    """
    Classify the student's query and reset tutor_drafts for the new turn.

    Returns dict slice updating ``task``, ``difficulty``, ``agent_thoughts``,
    and ``tutor_drafts=None`` (reset signal for the custom reducer).
    """
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
        result: SupervisorOutput = await _supervisor_llm.ainvoke(
            [HumanMessage(content=prompt)], config=config
        )
        task = result.task
        difficulty = result.difficulty
    except Exception as exc:  # noqa: BLE001
        logger.warning("Supervisor LLM failed, using defaults: %s", exc)
        task, difficulty = "qa", "medium"

    logger.info(
        "Supervisor → task=%s difficulty=%s weak_topics=%d",
        task, difficulty, len(weak_topics),
    )

    return {
        "task": task,
        "difficulty": difficulty,
        # CRITICAL: returning None through the _reset_or_add_drafts reducer
        # resets tutor_drafts to [] — prevents previous-turn stale drafts
        # from leaking into the current turn's synthesizer.
        "tutor_drafts": None,
        "agent_thoughts": [
            {
                "node": "supervisor",
                "summary": f"Task: {task} · Difficulty: {difficulty}",
                "data": {
                    "task": task,
                    "difficulty": difficulty,
                    "weak_topics": weak_topics,
                },
            }
        ],
    }
