"""
Node 2 — Query Rewriter

Transforms the student's conversational query into 2 retrieval-optimised
academic queries.  Two queries dramatically increase hybrid-search recall —
they are run in parallel by the RAG Agent.

Memory handling
---------------
Uses ``trim_messages`` to extract the last 6 messages from the conversation
history (3 turns of Q&A).  These are injected natively into the prompt via
``MessagesPlaceholder`` so the LLM can resolve pronouns and contextual
references ("explain that further", "relate that to the previous question").

LangChain best-practices applied
----------------------------------
* ``with_structured_output`` — guarantees parseable JSON; no regex hackery.
* ``ChatPromptTemplate`` + ``MessagesPlaceholder`` — passes conversation turns
  as proper role-aware messages (not a flat string), which fine-tuned LLMs
  handle significantly better.
* ``trim_messages`` — caps history at 6 messages using simple message-count
  strategy, guaranteeing context window safety with any Groq model.
* Module-level chain singleton — avoids cold construction inside hot path.
* ``@traceable`` — LangSmith span with ``name="query_rewriter"``.
"""
from __future__ import annotations

import logging

from langchain_core.messages import trim_messages
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
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

class RewriterOutput(BaseModel):
    rewrites: list[str] = Field(
        description="2 or 3 retrieval-optimised academic queries.",
        min_length=2,
        max_length=3,
    )


# ── Prompt template + LLM pool (module-level singletons) ────────────────────
# RoundRobinLLM.for_role("structured") rotates through JSON-capable models.
# The pool starts at a different index per request so load spreads across models.

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
        "  5. Produce exactly 3 diverse queries:\n"
        "     - Query 1: focused on definition/concept\n"
        "     - Query 2: focused on application/example\n"
        "     - Query 3: a CONTINUITY query — if the conversation history contains "
        "previous AI answers, extract the key terms/topics discussed and create a query "
        "that retrieves related content. If there is no history, make this a synonym/alternative "
        "phrasing of Query 1.\n\n"
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

_rewriter_llm = RoundRobinLLM.for_role("structured", temperature=0.1)

# NOTE: The chain is rebuilt per-request inside the node because
# with_structured_output must be re-applied on each round-robin attempt.
# See the node function below.


# ── Node ─────────────────────────────────────────────────────────────────────

@traceable(name="query_rewriter")
async def query_rewriter_node(state: AgentState, config: RunnableConfig) -> dict:
    """
    Rewrite the student query into 2 retrieval-optimised academic queries.

    Injects the trimmed conversation history into the prompt so pronoun
    resolution works correctly across turns.
    """
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
        structured_llm = _rewriter_llm.with_structured_output(RewriterOutput)
        # Format the prompt messages, then invoke the structured pool
        prompt_value = await _rewriter_prompt.ainvoke(
            {
                "task": task,
                "difficulty": difficulty,
                "history": history,
                "question": original,
            }
        )
        result: RewriterOutput = await structured_llm.ainvoke(
            prompt_value.to_messages(),
            config=config,
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
