"""
Node 7 — Critic Agent (Quality Gate)
Validates the Synthesizer's output against the retrieved source documents.
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

class CriticOutput(BaseModel):
    severity: str = Field(
        description="One of: none, low, high",
        pattern="^(none|low|high)$",
    )
    issues: list[str] = Field(
        description=(
            "Specific, actionable issues. "
            "For severity=high, each issue must name the exact paragraph/sentence "
            "and the conflicting source. Empty list if severity is not high."
        ),
        default_factory=list,
    )
    passed: bool = Field(
        description="True if the answer is acceptable for delivery to the student.",
    )
    required_facts: list[str] = Field(
        description="List of specific, verifiable facts from the sources that MUST be included correctly in the revision.",
        default_factory=list,
    )


# ── Node ─────────────────────────────────────────────────────────────────────

@traceable(name="critic_agent")
async def critic_agent_node(state: AgentState, config: RunnableConfig) -> dict:
    """
    Quality-gate the Synthesizer's answer.
    """
    # Lazy init to prevent import-time hangs
    llm = RoundRobinLLM.for_role(
        "structured", 
        temperature=0, 
        schema=CriticOutput
    )
    response_text = state.get("response_text", "")
    context_docs = state.get("context_docs", [])
    retry_count = state.get("retry_count", 0)

    # Build a compact source preview (avoid blowing out context window)
    source_lines = []
    for i, doc in enumerate(context_docs[:5], 1):
        meta = doc.get("metadata", {})
        title = meta.get("title", "?")
        content = doc.get("content", "")[:300]
        source_lines.append(f"[{i}] {title}:\n{content}")
    source_preview = "\n\n".join(source_lines) if source_lines else "(No sources retrieved)"

    prompt = f"""You are a rigorous academic fact-checker for an AI tutoring system.
Your task: identify hallucinations or inaccuracies in the response below.

Student Response (first 2000 chars):
{response_text[:2000]}

Source Documents:
{source_preview}

Evaluation criteria:
1. Does the response make claims that contradict the source documents?
2. Does the response cite sources it doesn't use, or misattribute content?
3. Are there formulae, numbers, or dates that are clearly wrong per the sources?

Rules for `required_facts`:
- For every error found, provide the CORRECT fact/formula from the source as a bullet point.
- If a major point is missing, provide a summary of that missing context.
- Keep facts atomic and grounded.

Example:
  ISSUE: "Claims gravity is 10 m/s2"
  REQUIRED_FACT: "Acceleration due to gravity is exactly 9.81 m/s2 per source [1]"

Return ONLY the structured JSON matching the required schema."""

    try:
        result: CriticOutput = await llm.ainvoke(
            [HumanMessage(content=prompt)], config=config
        )
        severity = result.severity
        issues = result.issues if severity == "high" else []
        passed = result.passed
    except Exception as exc:  # noqa: BLE001
        logger.warning("Critic LLM failed, defaulting to pass: %s", exc)
        severity, issues, passed = "none", [], True

    # Only send feedback if severity is high AND we haven't retried yet
    actionable_feedback = issues if (severity == "high" and retry_count < 1) else []
    new_retry_count = retry_count + (1 if severity == "high" and retry_count < 1 else 0)

    review = {
        "severity": severity,
        "issues": issues,
        "passed": passed,
        "required_facts": result.required_facts if severity == "high" else [],
    }

    logger.info(
        "Critic → severity=%s · pass=%s · issues=%d · retry_count=%d→%d",
        severity, passed, len(issues), retry_count, new_retry_count,
    )

    return {
        "critic_review": review,
        "critic_feedback": actionable_feedback,
        "retry_count": new_retry_count,
        "agent_thoughts": [
            {
                "node": "critic_agent",
                "summary": (
                    f"Quality: {severity} · Pass: {passed} · "
                    f"Issues: {len(issues)} · Retry: {bool(actionable_feedback)}"
                ),
                "data": review,
            }
        ],
    }
