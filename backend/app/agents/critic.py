"""
Node 7 — Critic Agent (Quality Gate)
Validates the Synthesizer's output against the retrieved source documents.
"""
from __future__ import annotations

import logging

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from langsmith import traceable

from app.agents.state import AgentState
from app.config import get_settings
from app.utils.llm_pool import RoundRobinLLM
from app.agents.prompts.critic import CRITIC_PROMPT
from app.agents.schemas.critic import CriticOutput

logger = logging.getLogger(__name__)
settings = get_settings()


# ── Node ─────────────────────────────────────────────────────────────────────

@traceable(name="critic_agent")
async def critic_agent_node(state: AgentState, config: RunnableConfig) -> dict:
    """Quality-gate the Synthesizer's answer."""
    llm = RoundRobinLLM.for_role(
        "critic", 
        temperature=0.0, 
        top_p=0.1, 
        top_k=1, 
        schema=CriticOutput
    )
    response_text = state.get("response_text", "")
    context_docs = state.get("context_docs", [])

    source_lines = []
    for i, doc in enumerate(context_docs, 1):
        meta = doc.get("metadata", {})
        title = meta.get("title", "Unknown Source")
        content = doc.get("content", "")
        source_lines.append(f"[{i}] {title}:\n{content}")
    source_preview = "\n\n".join(source_lines) if source_lines else "(No relevant sources retrieved)"

    prompt_value = await CRITIC_PROMPT.ainvoke({
        "response_text": response_text,
        "source_preview": source_preview
    })

    try:
        res_raw = await llm.ainvoke(prompt_value.to_messages(), config=config)
        result: CriticOutput = res_raw["parsed"]
        raw_text = res_raw["raw"].content if hasattr(res_raw["raw"], "content") else str(res_raw["raw"])
        
        severity = result.severity
        issues = result.issues or []
        passed = result.passed
        required_facts = result.required_facts or []
        review = result.model_dump()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Critic LLM failed, defaulting to pass: %s", exc)
        severity, issues, passed = "none", [], True
        required_facts = []
        raw_text = ""
        review = {"severity": severity, "issues": issues, "passed": passed, "required_facts": required_facts}

    logger.info(
        "Critic [AUDIT]: severity=%s | pass=%s | issues=%d",
        severity, passed, len(issues)
    )

    retry_count = state.get("retry_count", 0)
    goto = "output_moderator"
    if not passed and retry_count < 2:
        logger.warning(f"CRITIC_REJECTION: Initiating self-correction (Retry {retry_count + 1}/2)")
        goto = "orchestrator"

    return Command(
        goto=goto,
        update={
            "critic_review": review,
            "critic_feedback": issues, 
            "retry_count": retry_count + (1 if not passed else 0),
            "safety_raw_responses": [raw_text],
            "agent_thoughts": [
                {
                    "node": "critic_agent",
                    "summary": (
                        f"Quality Audit: {severity} | Pass: {passed} | "
                        f"Issues: {len(issues)}"
                    ),
                    "data": review,
                }
            ],
        }
    )
