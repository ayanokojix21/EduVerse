"""
Utilities for parsing LLM text output from agent nodes.

Every tutor / synthesizer prompt ends with two structured blocks:

    CITATIONS_JSON: [{"source_index":1,"title":"...","alternate_link":"...",
                      "content_type":"...","item_id":"...","snippet":"..."}]
    REASONING: one sentence on your approach

These helpers extract the free-form response text and the structured data
from a raw LLM content string.
"""
from __future__ import annotations

import json
import re

_CITATIONS_RE = re.compile(
    r"CITATIONS_JSON:\s*(\[.*?\])",
    re.DOTALL | re.IGNORECASE,
)
_REASONING_RE = re.compile(
    r"REASONING:\s*(.+?)(?:\n|$)",
    re.DOTALL | re.IGNORECASE,
)


def _extract_citations_block(text: str) -> tuple[str, list[dict]]:
    """
    Remove the CITATIONS_JSON block from *text* and return
    ``(clean_text, citations_list)``.
    """
    match = _CITATIONS_RE.search(text)
    if not match:
        return text.strip(), []

    raw_json = match.group(1)
    clean = text[: match.start()].strip()

    try:
        citations = json.loads(raw_json)
        if not isinstance(citations, list):
            citations = []
    except json.JSONDecodeError:
        citations = []

    return clean, citations


def _enrich_citations(
    citations: list[dict],
    context_docs: list[dict],
) -> list[dict]:
    """
    Back-fill metadata fields that the LLM may have omitted by consulting
    the original *context_docs* list (indexed via ``source_index - 1``).
    """
    enriched = []
    for cite in citations:
        idx = int(cite.get("source_index", 0)) - 1
        if 0 <= idx < len(context_docs):
            doc_meta = context_docs[idx].get("metadata", {})
            cite.setdefault("title", doc_meta.get("title", "Unknown"))
            cite.setdefault("alternate_link", doc_meta.get("alternate_link", "#"))
            cite.setdefault("content_type", doc_meta.get("content_type", "unknown"))
            cite.setdefault("item_id", doc_meta.get("item_id", ""))
            cite.setdefault("snippet", context_docs[idx].get("content", "")[:200])
        enriched.append(cite)
    return enriched


def parse_tutor_output(
    content: str,
    context_docs: list[dict],
) -> tuple[str, list[dict], str]:
    """
    Parse the raw LLM output from a tutor node.

    Returns
    -------
    (response_text, citations, reasoning)
    """
    # Remove REASONING block first
    reasoning = ""
    reasoning_match = _REASONING_RE.search(content)
    if reasoning_match:
        reasoning = reasoning_match.group(1).strip()
        content = content[: reasoning_match.start()].strip()

    response_text, citations = _extract_citations_block(content)
    citations = _enrich_citations(citations, context_docs)

    return response_text, citations, reasoning


def parse_response_and_citations(
    content: str,
    context_docs: list[dict],
) -> tuple[str, list[dict]]:
    """
    Parse the raw LLM output from the synthesizer node.

    Returns
    -------
    (response_text, citations)
    """
    response_text, citations = _extract_citations_block(content)
    citations = _enrich_citations(citations, context_docs)
    return response_text, citations
