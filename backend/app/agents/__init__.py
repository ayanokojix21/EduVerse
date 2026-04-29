"""
app/agents/__init__.py
───────────────────────
Public entry point for the EduVerse Multi-Agent System (MAS).

This package encapsulates the agentic logic, graph orchestration, 
and pedagogical intelligence of the EduVerse platform.
"""
from app.agents.state import AgentState
from app.agents.graph import build_graph, compile_graph, get_compiled_graph

__all__ = [
    "AgentState",
    "build_graph",
    "compile_graph",
    "get_compiled_graph",
]
