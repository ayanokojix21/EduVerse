"""
Node 7 — Critic Agent (Background Quality Logger)
Fires the LLM audit as a background task and immediately passes through.
Never retries or blocks the response pipeline.
"""
from __future__ import annotations

import asyncio
import logging

from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from langsmith import traceable

from app.agents.state import AgentState
from app.utils.llm_pool import RoundRobinLLM
from app.utils.thinking_utils import build_thought
from app.agents.prompts.critic import CRITIC_PROMPT
from app.agents.schemas.critic import CriticOutput

logger = logging.getLogger(__name__)


# ── Background Audit Task ────────────────────────────────────────────────────

async def _background_critic_audit(response_text: str, context_docs: list[dict]) -> None:
    """Fire-and-forget LLM quality audit. Logs results but never blocks the pipeline."""
    try:
        llm = RoundRobinLLM.for_role(
            "critic",
            temperature=0.0,
            top_p=0.1,
            top_k=1,
            schema=CriticOutput,
        )

        source_lines = []
        for i, doc in enumerate(context_docs, 1):
            meta = doc.get("metadata", {})
            title = meta.get("title", "Unknown Source")
            content = doc.get("content", "")
            source_lines.append(f"[{i}] {title}:\n{content}")
        source_preview = "\n\n".join(source_lines) if source_lines else "(No relevant sources retrieved)"

        prompt_value = await CRITIC_PROMPT.ainvoke({
            "response_text": response_text,
            "source_preview": source_preview,
        })

        res_raw = await llm.ainvoke(prompt_value.to_messages())
        result: CriticOutput = res_raw["parsed"]

        if result is None:
            logger.warning("Critic [BACKGROUND AUDIT]: Failed to parse structured output natively. Attempting robust extraction.")
            raw_text = res_raw.get("raw").content if isinstance(res_raw, dict) and hasattr(res_raw.get("raw"), "content") else getattr(res_raw, "content", str(res_raw))
            from app.utils.thinking_utils import extract_robust_json
            
            data = extract_robust_json(raw_text)
            if data:
                try:
                    if "passed" in data and isinstance(data["passed"], str):
                        data["passed"] = data["passed"].lower() == "true"
                    if "is_socratic" in data and isinstance(data["is_socratic"], str):
                        data["is_socratic"] = data["is_socratic"].lower() == "true"
                    result = CriticOutput(**data)
                except Exception as e:
                    logger.warning(f"Critic fallback parsing failed: {e}")
            
            if result is None:
                logger.warning("Critic [BACKGROUND AUDIT]: Fallback parsing failed entirely.")
                return

        logger.info(
            "Critic [BACKGROUND AUDIT]: severity=%s | pass=%s | issues=%d",
            result.severity,
            result.passed,
            len(result.issues or []),
        )
        if not result.passed:
            logger.warning(
                "Critic flagged issues (background only, no retry): %s",
                result.issues,
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Background critic audit failed (non-blocking): %s", exc)


# ── Node ─────────────────────────────────────────────────────────────────────

@traceable(name="critic_agent")
async def critic_agent_node(state: AgentState, config: RunnableConfig) -> Command:
    """Background quality logger — immediately passes through to output_moderator."""
    response_text = state.get("response_text", "")
    context_docs = state.get("context_docs", [])

    # Fire the LLM audit in the background — does NOT block the response
    asyncio.create_task(_background_critic_audit(response_text, context_docs))

    return Command(
        goto="output_moderator",
        update={
            "agent_thoughts": [build_thought(
                node="critic_agent",
                summary="Quality Audit — Logged (Background)",
                reasoning="Critic audit dispatched as background task. Response streamed immediately.",
            )],
        },
    )
