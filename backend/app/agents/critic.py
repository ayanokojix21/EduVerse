"""
Node 7 — Critic Agent  (Quality Gate)

Validates the Synthesizer's output against the retrieved source documents.
Uses a structured JSON output to produce an actionable quality review.

Decision logic
--------------
* severity == "none" | "low" → pass (graph proceeds to END)
* severity == "high" AND retry_count < 1 → graph loops back to Synthesizer
* severity == "high" AND retry_count >= 1 → pass anyway (one retry max)

The Critic uses specific, actionable language — not vague complaints.
For example:
  BAD:  "answer is incorrect"
  GOOD: "paragraph 2 states F=m/a but source [1] clearly shows F=ma"

This specificity is enforced in the prompt and validated by
``with_structured_output``.

LangChain best-practices
--------------------------
* ``with_structured_output`` for guaranteed JSON + Pydantic validation.
* temperature=0 for fully deterministic, reproducible quality gate.
* ``@traceable`` for LangSmith span.
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


# ── LLM pool (round-robin structured pool) ────────────────────────────
# temperature=0 for deterministic quality gate; JSON output required.

_critic_llm = RoundRobinLLM.for_role("structured", temperature=0).with_structured_output(
    CriticOutput
)


# ── Node ─────────────────────────────────────────────────────────────────────

@traceable(name="critic_agent")
async def critic_agent_node(state: AgentState, config: RunnableConfig) -> dict:
    """
    Quality-gate the Synthesizer's answer.

    Determines if the response contains hallucinations or contradictions
    vs. the retrieved source documents.  If so, feeds specific issues back
    to the Synthesizer for targeted correction (one retry max).
    """
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

IMPORTANT — specificity rules for issues:
  BAD: "The answer is wrong"
  GOOD: "Sentence 2 claims the formula is F=m/a but source [1] states F=ma"
  BAD: "Missing information"
  GOOD: "The 10N friction force mentioned in source [2] is not addressed"

If no significant issues are found, use severity="none" or severity="low".
Severity="high" should be reserved for factual contradictions with the sources.

Return ONLY the structured JSON matching the required schema."""

    try:
        result: CriticOutput = await _critic_llm.ainvoke(
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
