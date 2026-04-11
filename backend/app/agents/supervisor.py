"""
Node 1 — Supervisor

Classifies the incoming student query into:
  * task       : "qa" | "explain" | "quiz" | "feedback"
  * difficulty : "easy" | "medium" | "hard"

Uses a fast 8B Groq model with temperature=0 to guarantee deterministic
JSON output on every call.  The node is decorated with @traceable so every
invocation creates a named span in LangSmith.

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


# ── LLM (module-level singleton, avoids re-creation per request) ─────────────

_supervisor_llm = ChatGroq(
    model=settings.groq_supervisor_model,
    temperature=0,
    api_key=settings.groq_api_key,
).with_structured_output(SupervisorOutput)


# ── Node ─────────────────────────────────────────────────────────────────────

@traceable(name="supervisor")
async def supervisor_node(state: AgentState, config: RunnableConfig) -> dict:
    """
    Classify the student's query.

    Returns dict slice updating ``task``, ``difficulty``, and
    ``agent_thoughts``.
    """
    query = state["original_query"]

    prompt = (
        "You are a routing agent for an AI tutoring system.\n"
        "Classify the student question below into exactly one task type and one difficulty.\n\n"
        "task options  : qa (factual question), explain (concept explanation), "
        "quiz (practice question), feedback (student writing/work review), "
        "timetable (schedule/email events)\n"
        "difficulty options: easy, medium, hard\n\n"
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

    logger.info("Supervisor → task=%s difficulty=%s", task, difficulty)

    return {
        "task": task,
        "difficulty": difficulty,
        "agent_thoughts": [
            {
                "node": "supervisor",
                "summary": f"Task: {task} · Difficulty: {difficulty}",
                "data": {"task": task, "difficulty": difficulty},
            }
        ],
    }
