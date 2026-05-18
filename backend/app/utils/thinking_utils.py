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


def normalize_content(raw_content: Any, include_thinking: bool = False) -> str:
    """Normalize Gemma 4's multimodal/thinking list format to a plain string.
    
    Gemma 4 models can return content as:
      - A plain string
      - A list of dicts with 'text', 'thinking', or other keys
    
    Args:
        raw_content: The raw content from the LLM response.
        include_thinking: If False (default), only 'text' parts are included
                          in the output — thinking/reasoning is stripped.
                          Set True when you need the full content for
                          extract_thinking() or internal logging.
    
    Returns:
        A single plain string.
    """
    if isinstance(raw_content, list):
        parts: list[str] = []
        for part in raw_content:
            if isinstance(part, dict):
                part_type = part.get("type", "")
                if part_type == "thinking" and not include_thinking:
                    continue
                text_val = part.get("text") or (part.get("thinking") if include_thinking else None)
                if text_val:
                    parts.append(str(text_val))
            else:
                parts.append(str(part))
        return "\n".join(parts)
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
    # For Gemma 4 list format: extract thinking parts directly
    if isinstance(raw_content, list):
        thinking_parts = []
        for part in raw_content:
            if isinstance(part, dict) and part.get("type") == "thinking":
                val = part.get("thinking", "")
                if val:
                    thinking_parts.append(str(val).strip())
        if thinking_parts:
            return "\n".join(thinking_parts)
    
    # Fallback: regex extraction from string content
    text = normalize_content(raw_content, include_thinking=True)
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

def extract_robust_json(raw_text: Any) -> dict | None:
    """
    Safely extract and parse JSON from a raw LLM string.
    Handles markdown blocks and non-strict JSON (like single quotes).
    """
    import json
    import ast
    from langchain_core.utils.json import parse_json_markdown
    
    # Normalize list-based contents from Gemma 4 to a plain string
    # We include thinking just in case the model placed the JSON inside the block.
    normalized_text = normalize_content(raw_text, include_thinking=True)
    
    try:
        # First try Langchain's built in markdown JSON parser
        parsed = parse_json_markdown(normalized_text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    
    # Find all non-greedy {...} blocks
    matches = re.finditer(r"(\{.*?\})", normalized_text, re.DOTALL)
    
    for match in matches:
        json_str = match.group(1)
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass
            
        try:
            # Fix booleans and nulls for python ast
            python_str = json_str.replace("true", "True").replace("false", "False").replace("null", "None")
            parsed = ast.literal_eval(python_str)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
            
    return None
