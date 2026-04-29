from __future__ import annotations

import logging
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from app.agents.critic import critic_agent_node
from app.agents.orchestrator import orchestrator_node
from app.agents.rag_subgraph import build_rag_subgraph
from app.agents.state import AgentState
from app.agents.quiz_subgraph import build_quiz_subgraph
from app.agents.feedback_subgraph import build_feedback_subgraph
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_compiled_graph = None

def build_graph() -> StateGraph:
    """Assembles the EduVerse Multi-Agent System."""
    g: StateGraph = StateGraph(AgentState)

    from app.agents.guardrails import Guardrails
    g.add_node('input_moderator',   Guardrails.input_moderator)
    g.add_node('integrity_guard',   Guardrails.academic_integrity_check)
    g.add_node('output_moderator',  Guardrails.output_moderator)

    # Core Nodes
    g.add_node('orchestrator',      orchestrator_node)
    g.add_node('quiz_swarm',        build_quiz_subgraph())
    g.add_node('feedback_swarm',    build_feedback_subgraph())
    g.add_node('rag_swarm',         build_rag_subgraph())
    g.add_node('critic_agent',      critic_agent_node)

    # ── Entry Path (Security First) ──────────────────────────────────────────
    g.add_edge(START, 'input_moderator')

    
    # ── Completion & Safety Shield ───────────────────────────────────────────
    g.add_edge('feedback_swarm', 'critic_agent')
    g.add_edge('rag_swarm',      'critic_agent')
    g.add_edge('quiz_swarm',     'critic_agent')
    g.add_edge('critic_agent',   'output_moderator')

    # Final Exit
    g.add_edge('output_moderator', END)

    return g

async def compile_graph(checkpointer):
    logger.info('Compiling EduVerse MAS...')
    compiled = build_graph().compile(checkpointer=checkpointer)
    global _compiled_graph
    _compiled_graph = compiled
    return compiled

def get_compiled_graph():
    if _compiled_graph is None:
        raise RuntimeError('LangGraph has not been compiled.')
    return _compiled_graph
