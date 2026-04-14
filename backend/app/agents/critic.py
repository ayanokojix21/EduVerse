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

    # Build a compact source preview (avoid blowing out context window)
    source_lines = []
    for i, doc in enumerate(context_docs[:10], 1):
        meta = doc.get("metadata", {})
        title = meta.get("title", "?")
        content = doc.get("content", "")[:350]
        source_lines.append(f"[{i}] {title}:\n{content}")
    source_preview = "\n\n".join(source_lines) if source_lines else "(No relevant sources retrieved)"

    prompt = f"""You are a rigorous but fair academic fact-checker.
Your task: Identify active hallucinations or contradictions in the Response based ONLY on the provided Sources.

RESPONSE:
{response_text[:2500]}

SOURCES:
{source_preview}

EVALUATION RULES:
1. SEVERITY=HIGH: Only if the Response explicitly CONTRADICTS a fact in the Sources (e.g. Doc says 1914, Response says 1920).
2. SEVERITY=LOW: If the Response makes a claim that is NOT in the Sources but sounds like "Common Knowledge" (e.g. "Paris is the capital of France").
3. SEVERITY=NONE: If every claim is perfectly supported by the Sources.

PASSED CRITERIA:
- Set `passed=False` ONLY if there is a CONFIRMED ERROR (Severity=High).
- If the info is helpful and factually sounds but not in the specific source snippets provided, set `passed=True` but `severity=low`.

Return ONLY the structured JSON matching the schema."""

    try:
        result: CriticOutput = await llm.ainvoke(
            [HumanMessage(content=prompt)], config=config
        )
        severity = result.severity
        issues = result.issues if severity == "high" else []
        passed = result.passed
        required_facts = result.required_facts if severity == "high" else []
    except Exception as exc:  # noqa: BLE001
        logger.warning("Critic LLM failed, defaulting to pass: %s", exc)
        severity, issues, passed = "none", [], True
        required_facts = []

    review = {
        "severity": severity,
        "issues": issues,
        "passed": passed,
        "required_facts": required_facts,
    }

    logger.info(
        "Critic → severity=%s · pass=%s · issues=%d",
        severity, passed, len(issues)
    )

    return {
        "critic_review": review,
        "agent_thoughts": [
            {
                "node": "critic_agent",
                "summary": (
                    f"Quality: {severity} · Pass: {passed} · "
                    f"Issues: {len(issues)}"
                ),
                "data": review,
            }
        ],
    }
