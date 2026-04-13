"""
LangGraph — Graph Wiring & Compilation
"""
from __future__ import annotations

import logging
from typing import Literal

from fastapi import FastAPI
from langgraph.graph import END, START, StateGraph

from app.agents.critic import critic_agent_node
from app.agents.orchestrator import orchestrator_node
from app.agents.rag_agent import rag_agent_node
from app.agents.state import AgentState
from app.agents.synthesizer import synthesizer_node
from app.agents.email_agent import email_agent_node
from app.agents.timetable_agent import timetable_agent_node
from app.agents.tutor_subgraph import build_tutor_subgraph
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Module-level compiled graph singleton — set once during app startup
_compiled_graph = None


# ── Conditional edges ────────────────────────────────────────────────────────

def route_orchestrator(state: AgentState) -> Literal["email_agent", "rag_agent"]:
    """
    Routing edge after orchestrator.
    Branches to the timetable pipeline if the task is 'timetable'.
    Otherwise proceeds to the standard RAG tutoring pipeline.
    """
    if state.get("task") == "timetable":
        return "email_agent"
    return "rag_agent"


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
    Assemble and return the uncompiled modern StateGraph.
    Uses subgraphs for specialized parallel components.
    """
    g: StateGraph = StateGraph(AgentState)

    # 1. Register Core Nodes
    g.add_node("orchestrator",    orchestrator_node)
    g.add_node("rag_agent",       rag_agent_node)
    g.add_node("synthesizer",     synthesizer_node)
    g.add_node("critic_agent",    critic_agent_node)
    g.add_node("email_agent",     email_agent_node)
    g.add_node("timetable_agent", timetable_agent_node)

    # 2. Register Specialized Subgraphs
    g.add_node("tutor_ensemble", build_tutor_subgraph())

    # ── Orchestration ────────────────────────────────────────────────────────

    # Route after orchestrator
    g.add_edge(START, "orchestrator")
    g.add_conditional_edges(
        "orchestrator",
        route_orchestrator,
        {
            "email_agent": "email_agent",
            "rag_agent": "rag_agent"
        },
    )

    # Standard RAG branch
    g.add_edge("rag_agent", "tutor_ensemble")
    g.add_edge("tutor_ensemble", "synthesizer")
    g.add_edge("synthesizer", "critic_agent")

    # Retry loop
    g.add_conditional_edges(
        "critic_agent",
        should_retry_synthesizer,
        {"synthesizer": "synthesizer", END: END},
    )

    # Timetable branch
    g.add_edge("email_agent",     "timetable_agent")
    g.add_edge("timetable_agent", END)

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
