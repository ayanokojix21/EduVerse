"""
app/utils/thinking_utils.py
─────────────────────────────
Shared utilities for extracting model reasoning and building
standardized agent_thought dicts for the SSE pipeline.

Gemma 4 and Gemini models embed chain-of-thought reasoning in
<think>...</think> blocks. This module provides helpers to:
  1. Extract that reasoning from raw LLM responses
  2. Build structured thought objects for the frontend
"""
from __future__ import annotations

import re
from typing import Any


# ── Regex for <think> blocks ─────────────────────────────────────────────────

_THINK_PATTERN = re.compile(
    r"<think>(.*?)</think>",
    re.DOTALL | re.IGNORECASE,
)


def normalize_content(raw_content: Any) -> str:
    """Normalize Gemma 4's multimodal/thinking list format to a plain string.
    
    Gemma 4 models can return content as:
      - A plain string
      - A list of dicts with 'text', 'thinking', or other keys
    
    This function handles both cases and returns a single string.
    """
    if isinstance(raw_content, list):
        return "\n".join(
            (part.get("text") or part.get("thinking") or str(part))
            if isinstance(part, dict) else str(part)
            for part in raw_content
        )
    return str(raw_content) if raw_content else ""


def extract_thinking(raw_content: Any) -> str:
    """Extract the content of <think>...</think> blocks from an LLM response.
    
    Args:
        raw_content: Raw response content — either a string or Gemma 4's
                     list-of-dicts format.
    
    Returns:
        The concatenated text inside all <think> blocks, or an empty string
        if no thinking blocks are found.
    """
    text = normalize_content(raw_content)
    matches = _THINK_PATTERN.findall(text)
    if not matches:
        return ""
    return "\n".join(m.strip() for m in matches if m.strip())


def build_thought(
    node: str,
    summary: str,
    reasoning: str = "",
    data: dict | None = None,
) -> dict:
    """Build a standardized agent_thought dict for the SSE pipeline.
    
    Args:
        node: The agent node name (e.g., 'planner', 'generator').
        summary: A short, bold-worthy header (e.g., "Optimizing Search Query").
        reasoning: The model's chain-of-thought reasoning (italic body text).
                   If empty, only the summary is shown.
        data: Optional structured metadata (scores, labels, etc.).
    
    Returns:
        A dict matching the AgentThought frontend interface::
        
            {
                "node": "planner",
                "summary": "Optimizing Search Query",
                "reasoning": "I'm rewriting the query to expand...",
                "data": {"rewritten": "..."}
            }
    """
    thought: dict = {
        "node": node,
        "summary": summary,
    }
    if reasoning:
        thought["reasoning"] = reasoning
    if data:
        thought["data"] = data
    return thought
