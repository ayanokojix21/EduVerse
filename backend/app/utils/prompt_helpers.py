"""
Prompt Helpers

Shared utilities for consistent context formatting across all LLM agents.
Ensures that Tutor A, Tutor B, and the Synthesizer always see course materials
in the same high-density, citation-friendly format.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

def build_context_text(context_docs: list[dict]) -> str:
    """
    Render numbered context passages for the prompt.
    Used by tutors to generate drafts and by the synthesizer for grounded merging.
    """
    if not context_docs:
        return (
            "(No specific classroom content was retrieved for this query. "
            "Use your general knowledge to help, but clearly inform the student "
            "that this answer is based on general knowledge rather than their course materials.)"
        )
        
    lines = []
    for i, doc in enumerate(context_docs, 1):
        # Handle both LangChain Document objects and plain dicts
        content = getattr(doc, "page_content", doc.get("content", ""))
        meta = getattr(doc, "metadata", doc.get("metadata", {}))
        
        title = meta.get("title", "Unknown Source")
        link = meta.get("alternate_link", "No Link Available")
        file_url = meta.get("attachment_url", "")
        page = meta.get("page_number", "")
        page_str = f" | PAGE: {page}" if page else ""
        
        # We include the source index [i] to encourage consistent citation [1], [2], etc.
        header = f"--- SOURCE_{i}{page_str} ---\nTITLE: {title}\nLINK: {link}"
        if file_url:
            header += f"\nFILE_URL: {file_url}"
        
        lines.append(f"{header}\nCONTENT:\n{content}")
        
    return "\n\n".join(lines)
