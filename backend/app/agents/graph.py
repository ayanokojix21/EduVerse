from __future__ import annotations

import logging
from langgraph.graph import END, START, StateGraph

from app.agents.critic import critic_agent_node
from app.agents.orchestrator import orchestrator_node
from app.agents.rag_subgraph import build_rag_subgraph
from app.agents.state import AgentState
from app.agents.quiz_subgraph import build_quiz_subgraph
from app.agents.feedback_subgraph import build_feedback_subgraph

logger = logging.getLogger(__name__)
# NOTE: settings resolved lazily inside functions, not at module level.

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
    # input_moderator  → Command(goto='integrity_guard' | END)   [Command-routed]
    # integrity_guard  → Command(goto='orchestrator'  | END)     [Command-routed]
    # orchestrator     → Command(goto='rag_swarm'|'quiz_swarm'|'feedback_swarm') [Command-routed]

    # ── Completion & Safety Shield ───────────────────────────────────────────
    g.add_edge('feedback_swarm', 'critic_agent')
    g.add_edge('rag_swarm',      'critic_agent')
    g.add_edge('quiz_swarm',     'critic_agent')
    # critic_agent_node returns Command(goto='output_moderator' | 'orchestrator')
    # No static add_edge — would cause double-routing on the retry (orchestrator) path.

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
