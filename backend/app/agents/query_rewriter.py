"""
Node 2 — Query Rewriter
Transforms the conversational query into retrieval-optimised academic queries.
"""
from __future__ import annotations

import logging

from langchain_core.messages import trim_messages
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableConfig
from langsmith import traceable
from pydantic import BaseModel, Field

from app.agents.state import AgentState
from app.config import get_settings
from app.utils.llm_pool import RoundRobinLLM

logger = logging.getLogger(__name__)
settings = get_settings()


# ── Structured output schema ─────────────────────────────────────────────────

class RewriterOutput(BaseModel):
    rewrites: list[str] = Field(
        description="1 retrieval-optimised search query string. DO NOT answer the question here.",
        min_length=1,
        max_length=1,
    )


# ── Prompt template + LLM pool (module-level singletons) ────────────────────

_rewriter_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a retrieval query optimizer for an educational RAG system.\n\n"
        "Rules:\n"
        "  1. Remove conversational filler (can you, please explain, what is, etc.).\n"
        "  2. Preserve ALL domain-specific terms, formula names, and proper nouns exactly.\n"
        "  3. Expand acronyms if unambiguous.\n"
        "  4. Make each query standalone — resolve ALL pronouns and references "
        "(like 'that', 'it', 'this topic', 'the second one', 'explain more') "
        "by replacing them with the actual terms from the conversation history.\n"
        "  5. Produce exactly 1 search engine query string. It should succinctly capture the core concepts.\n"
        "  6. DO NOT write an answer to the question. You are ONLY generating a keyword search string to query a vector database.\n\n"
        "IMPORTANT: Look carefully at the previous AI assistant messages in the history. "
        "If the student says something vague like 'tell me more' or 'explain that', "
        "you MUST identify exactly what 'that' refers to from the last AI answer "
        "and write concrete, specific queries about it.\n\n"
        "Task: {task} | Difficulty: {difficulty}\n\n"
        "Return ONLY structured JSON matching the required schema.",
    ),
    MessagesPlaceholder("history", optional=True),
    ("human", "{question}"),
])

# ── Node ─────────────────────────────────────────────────────────────────────

@traceable(name="query_rewriter")
async def query_rewriter_node(state: AgentState, config: RunnableConfig) -> dict:
    """
    Rewrite the student query into retrieval-optimised academic queries.
    """
    # Lazy init to prevent import-time hangs
    llm = RoundRobinLLM.for_role(
        "structured", 
        temperature=0.1, 
        schema=RewriterOutput
    )
    original = state["original_query"]
    task = state.get("task", "qa")
    difficulty = state.get("difficulty", "medium")

    # Trim to last 6 messages (3 Q&A turns) by message count.
    # token_counter=len counts messages not tokens — fast and deterministic.
    history = trim_messages(
        state["messages"],
        strategy="last",
        token_counter=len,
        max_tokens=6,
        start_on="human",
        include_system=False,
    )

    try:
        prompt_value = await _rewriter_prompt.ainvoke(
            {
                "task": task,
                "difficulty": difficulty,
                "history": history,
                "question": original,
            }
        )
        result: RewriterOutput = await llm.ainvoke(
            prompt_value.to_messages(),
            config=config,
        )
        rewrites = result.rewrites
    except Exception as exc:  # noqa: BLE001
        logger.warning("Query rewriter failed, using original query: %s", exc)
        rewrites = [original]

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
