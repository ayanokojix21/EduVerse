from __future__ import annotations
import logging
import tiktoken
from typing import Any

logger = logging.getLogger(__name__)

# Enterprise safe budget for small context models (Groq preview tiers)
DEFAULT_MAX_TOKENS = 6000
CL100K_ENCODING = tiktoken.get_encoding("cl100k_base") # Llama-3/Qwen use compatible encodings

def count_tokens(text: str) -> int:
    """Return the number of tokens in a string."""
    return len(CL100K_ENCODING.encode(text))

def truncate_context_docs(
    context_docs: list[dict], 
    max_tokens: int = DEFAULT_MAX_TOKENS
) -> list[dict]:
    """
    Truncates the list of context documents to stay within a token budget.
    Preserves the highest-ranked documents first (assumes docs are sorted by relevance).
    """
    if not context_docs:
        return []

    total_tokens = 0
    pruned_docs = []
    
    for i, doc in enumerate(context_docs):
        # We estimate the token count of the rendered format (header + content)
        content = getattr(doc, "page_content", doc.get("content", ""))
        meta = getattr(doc, "metadata", doc.get("metadata", {}))
        
        # A rough estimate of the header size in tokens
        header_text = f"--- SOURCE_{i+1} ---\nTITLE: {meta.get('title')}\nLINK: {meta.get('alternate_link')}\nCONTENT:\n"
        doc_tokens = count_tokens(header_text + content)
        
        if total_tokens + doc_tokens > max_tokens:
            logger.warning(
                "Context limit reached (%d tokens). Dropping %d remaining documents.",
                total_tokens,
                len(context_docs) - i
            )
            break
            
        total_tokens += doc_tokens
        pruned_docs.append(doc)
        
    return pruned_docs

def get_token_budget_for_model(model_id: str) -> int:
    """
    Return a safe token budget for specific models.
    Models like qwen/qwen3-32b on Groq have extremely tight TPM limits (6k).
    """
    if "qwen" in model_id.lower() or "8b" in model_id.lower():
        return 5500 # Slightly under 6k to allow for prompt overhead
    return DEFAULT_MAX_TOKENS
