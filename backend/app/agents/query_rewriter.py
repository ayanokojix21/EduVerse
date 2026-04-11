"""
Node 2 — Query Rewriter

Transforms the student's conversational query into 2 retrieval-optimised
academic queries.  Two queries dramatically increase hybrid-search recall —
they are run in parallel by the RAG Agent.

LangChain best-practices applied
----------------------------------
* ``with_structured_output`` — guarantees parseable JSON; no regex hackery.
* Module-level LLM singleton — avoids cold construction inside hot path.
* ``@traceable`` — LangSmith span with ``name="query_rewriter"``.
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

class RewriterOutput(BaseModel):
    rewrites: list[str] = Field(
        description="Exactly 2 retrieval-optimised academic queries.",
        min_length=2,
        max_length=2,
    )


# ── LLM singleton ────────────────────────────────────────────────────────────

_rewriter_llm = ChatGroq(
    model=settings.groq_rewriter_model,
    temperature=0.1,
    api_key=settings.groq_api_key,
).with_structured_output(RewriterOutput)


# ── Node ─────────────────────────────────────────────────────────────────────

@traceable(name="query_rewriter")
async def query_rewriter_node(state: AgentState, config: RunnableConfig) -> dict:
    """
    Rewrite the student query into 2 retrieval-optimised academic queries.

    Removes filler words, resolves pronouns with context, preserves all
    domain-specific terms.  Returns exactly 2 queries for parallel retrieval.
    """
    original = state["original_query"]
    task = state.get("task", "qa")
    difficulty = state.get("difficulty", "medium")

    prompt = (
        "You are a retrieval query optimizer for an educational RAG system.\n\n"
        "Rules:\n"
        "  1. Remove conversational filler («can you», «please explain», «what is», etc.).\n"
        "  2. Preserve ALL domain-specific terms, formula names, and proper nouns exactly.\n"
        "  3. Expand acronyms if unambiguous.\n"
        "  4. Make each query standalone (no pronouns that need context).\n"
        "  5. Produce exactly 2 diverse queries — one focused on definition/concept, "
        "one focused on application/example.\n\n"
        f"Task type: {task} | Difficulty: {difficulty}\n"
        f"Student question: {original}\n\n"
        "Return ONLY structured JSON matching the required schema."
    )

    try:
        result: RewriterOutput = await _rewriter_llm.ainvoke(
            [HumanMessage(content=prompt)], config=config
        )
        rewrites = result.rewrites
    except Exception as exc:  # noqa: BLE001
        logger.warning("Query rewriter failed, using original query: %s", exc)
        rewrites = [original, original]

    logger.info("Query rewriter → %d queries produced", len(rewrites))

    return {
        "rewritten_queries": rewrites,
        "agent_thoughts": [
            {
                "node": "query_rewriter",
                "summary": f"Produced {len(rewrites)} retrieval queries",
                "data": {"queries": rewrites},
            }
        ],
    }
