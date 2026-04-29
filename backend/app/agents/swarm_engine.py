"""
app/agents/swarm_engine.py
──────────────────────────
MAS Engine — Standardizes the 'Audit-Revision' cycle across 
all specialized swarms. This decouples the state transition logic 
from the functional node implementations.
"""
from __future__ import annotations

import logging
from typing import Any, Literal

from langchain_core.messages import ToolMessage, AIMessage
from langgraph.types import Command

logger = logging.getLogger(__name__)

class SwarmLoop:
    """
    Standardized engine for managing agentic revision loops.
    Uniformly handles rejection logging, DPO pair extraction, and 
    state-wipe signals.
    """

    @staticmethod
    def handle_rejection(
        target_node: str,
        current_revisions: int,
        tc_id: str,
        llm_res: AIMessage,
        current_draft: Any,
        state_keys: dict[str, str]
    ) -> Command:
        """
        Generates a standardized Rejection Command.
        - update_keys: e.g. {'revisions': 'rag_revisions', 'rejected': 'rag_rejected_draft'}
        """
        rev_key = state_keys.get("revisions", "revisions")
        rej_key = state_keys.get("rejected", "rejected_draft")
        curr_key = state_keys.get("current", "current_draft")

        update = {
            "messages": [llm_res, ToolMessage(content="Critique sent to drafter.", tool_call_id=tc_id)],
            rev_key: current_revisions + 1,
            rej_key: current_draft
        }
        
        if state_keys.get("reset_signal"):
            update[curr_key] = [None]

        return Command(goto=target_node, update=update)

    @staticmethod
    def extract_dpo_pairs(
        agent_name: str,
        original_query: str,
        chosen_content: str,
        rejected_content: str,
        revision_count: int,
        critique: str = "Validator forced refinement."
    ) -> list[dict]:
        """
        Standardizes the collection of DPO (Direct Preference Optimization) pairs.
        Essential for future model fine-tuning.
        """
        if revision_count > 0 and rejected_content:
            return [{
                "agent": agent_name,
                "prompt": original_query,
                "chosen": chosen_content,
                "rejected": rejected_content,
                "critique": critique
            }]
        return []
