"""
Tutor Ensemble Subgraph

This subgraph manages the parallel execution of multiple pedagogical personalities.
It isolates the 'Tutor Personas' from the main RAG orchestration graph, 
making the system modular and easier to scale with new tutors.
"""
from __future__ import annotations

import logging

from langgraph.graph import END, START, StateGraph

from app.agents.state import AgentState
from app.agents.tutor_a import tutor_agent_a_node
from app.agents.tutor_b import tutor_agent_b_node

logger = logging.getLogger(__name__)

class TutorSubgraphState(AgentState):
    """
    Subgraphs share the parent state schema.
    We leverage the same reducers (like tutor_drafts) to fan-in results.
    """
    pass

def build_tutor_subgraph() -> StateGraph:
    """
    Build a subgraph that runs Tutor A and Tutor B in parallel 
    and returns their combined drafts.
    """
    workflow = StateGraph(TutorSubgraphState)

    workflow.add_node("tutor_a", tutor_agent_a_node)
    workflow.add_node("tutor_b", tutor_agent_b_node)

    workflow.add_edge(START, "tutor_a")
    workflow.add_edge(START, "tutor_b")
    
    workflow.add_edge("tutor_a", END)
    workflow.add_edge("tutor_b", END)

    return workflow.compile()
