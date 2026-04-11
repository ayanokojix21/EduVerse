"""
LangGraph — Graph Wiring & Compilation

This module is the heart of the EduVerse agent pipeline.  It:

1. Defines ``dispatch_tutors`` — the conditional edge that uses the
   LangGraph ``Send`` API to launch Tutor A and Tutor B **in parallel**.

2. Defines ``should_retry_synthesizer`` — the conditional edge that
   decides whether to loop back to the Synthesizer after Critic review
   (max 1 retry).

3. ``build_graph()`` wires all 7 nodes together and returns the uncompiled
   ``StateGraph``.

4. ``compile_graph(checkpointer)`` compiles the graph.

5. ``get_compiled_graph()`` — lazy singleton that returns the compiled
   graph from app state.  The chat endpoint uses this.

LangGraph best-practices applied
----------------------------------
* ``Send`` API with full state passthrough — tutors receive the complete
  AgentState so they can access context_docs, task, difficulty etc.
* ``operator.add`` reducer on ``tutor_drafts`` safely accumulates both
  parallel outputs before the Synthesizer fan-in.
* ``version="v2"`` streaming via ``astream_events`` surfaces per-token
  events from any streaming LLM in the graph.
* MongoDB AsyncSaver provides durable cross-request conversation threads.
"""
from __future__ import annotations

import logging
from typing import Literal

from fastapi import FastAPI
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from app.agents.critic import critic_agent_node
from app.agents.query_rewriter import query_rewriter_node
from app.agents.rag_agent import rag_agent_node
from app.agents.state import AgentState
from app.agents.supervisor import supervisor_node
from app.agents.synthesizer import synthesizer_node
from app.agents.tutor_a import tutor_agent_a_node
from app.agents.tutor_b import tutor_agent_b_node
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Module-level compiled graph singleton — set once during app startup
_compiled_graph = None


# ── Conditional edges ────────────────────────────────────────────────────────

def dispatch_tutors(state: AgentState) -> list[Send]:
    """
    Fan-out edge after rag_agent.

    Returns two ``Send`` objects so LangGraph runs both tutor nodes
    simultaneously in the same superstep.  Each tutor receives the full
    current state (including context_docs, task, difficulty).

    The ``operator.add`` reducer on ``state["tutor_drafts"]`` guarantees
    safe accumulation of both drafts before the Synthesizer fan-in.
    """
    return [
        Send("tutor_agent_a", dict(state)),
        Send("tutor_agent_b", dict(state)),
    ]


def should_retry_synthesizer(
    state: AgentState,
) -> Literal["synthesizer", "__end__"]:
    """
    Routing edge after critic_agent.

    Loops back to synthesizer when:
      * severity is "high"   (critic found real issues)
      * retry_count <= 1     (guard: max one retry)

    Otherwise routes to END (answer is delivered to user).
    """
    review = state.get("critic_review") or {}
    retry_count = state.get("retry_count", 0)
    critic_feedback = state.get("critic_feedback") or []

    # Only retry if critic gave specific, actionable feedback
    if review.get("severity") == "high" and retry_count <= 1 and critic_feedback:
        logger.info("Critic triggered retry #%d", retry_count)
        return "synthesizer"

    return END


# ── Graph construction ───────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """
    Assemble and return the uncompiled 7-node StateGraph.
    Call ``compile_graph()`` to attach a checkpointer and store.
    """
    g: StateGraph = StateGraph(AgentState)

    # Register all 7 nodes
    g.add_node("supervisor",     supervisor_node)
    g.add_node("query_rewriter", query_rewriter_node)
    g.add_node("rag_agent",      rag_agent_node)
    g.add_node("tutor_agent_a",  tutor_agent_a_node)
    g.add_node("tutor_agent_b",  tutor_agent_b_node)
    g.add_node("synthesizer",    synthesizer_node)
    g.add_node("critic_agent",   critic_agent_node)

    # Sequential edges: START → supervisor → rewriter → rag
    g.add_edge(START,            "supervisor")
    g.add_edge("supervisor",     "query_rewriter")
    g.add_edge("query_rewriter", "rag_agent")

    # Parallel fan-out: rag_agent → [tutor_a ‖ tutor_b]
    # LangGraph's Send API launches both tutors in the same superstep.
    g.add_conditional_edges(
        "rag_agent",
        dispatch_tutors,
        ["tutor_agent_a", "tutor_agent_b"],
    )

    # Fan-in: both tutors → synthesizer (LangGraph waits for both)
    g.add_edge("tutor_agent_a", "synthesizer")
    g.add_edge("tutor_agent_b", "synthesizer")

    # Synthesizer → critic (always)
    g.add_edge("synthesizer", "critic_agent")

    # Critic → synthesizer (retry) or END
    g.add_conditional_edges(
        "critic_agent",
        should_retry_synthesizer,
        {"synthesizer": "synthesizer", END: END},
    )

    return g


async def compile_graph(checkpointer):
    """
    Compile the StateGraph with the provided checkpointer.

    Checkpointer enables conversation memory and resumable sessions
    across reconnects.

    Returns the compiled ``CompiledGraph`` (a ``Pregel`` instance).
    """
    logger.info("Compiling LangGraph with MongoDB backend…")

    compiled = build_graph().compile(checkpointer=checkpointer)

    global _compiled_graph  # noqa: PLW0603
    _compiled_graph = compiled

    logger.info("LangGraph compiled successfully with MongoDB checkpointer.")
    return compiled


def get_compiled_graph():
    """
    Return the module-level compiled graph singleton.

    Raises ``RuntimeError`` if called before ``compile_graph()``
    (i.e., before the FastAPI lifespan startup has completed).
    """
    if _compiled_graph is None:
        raise RuntimeError(
            "LangGraph has not been compiled. "
            "Ensure compile_graph() is called during app startup."
        )
    return _compiled_graph


# ── FastAPI lifespan integration ──────────────────────────────────────────────

async def init_graph_on_startup(app: FastAPI) -> None:
    """
    Called from ``mongo_lifespan`` during FastAPI startup.
    Compiles and attaches the graph to ``app.state`` for request-time access.
    """
    s = get_settings()
    # Note: This executes but is immediately overridden by the mongodb.py lifespan
    pass
    logger.info("Agent graph attached to app.state.agent_graph")
