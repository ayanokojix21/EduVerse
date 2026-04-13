"""
Helper functions for explaining the RAG retrieval process.
Directly from Cohere Rerank probabilities (0-1).
"""
from __future__ import annotations

from langchain_core.documents import Document


# ── Confidence thresholds ────────────────────────────────────────────────────

_HIGH_THRESHOLD   = 0.70
_MEDIUM_THRESHOLD = 0.40


def _confidence_label_and_narrative(
    top_score: float,
    retrieval_label: str,
) -> tuple[str, str]:
    """
    Derive the confidence level and narrative text based on the reranker logit/probability.
    Since we shifted to CohereRerank (0-1), these thresholds are now direct probabilities.
    """
    if top_score >= _HIGH_THRESHOLD:
        return (
            "High",
            f"Strong classroom match ({top_score:.0%} relevance). "
            "The answer is precisely grounded in your course materials.",
        )
    if top_score >= _MEDIUM_THRESHOLD:
        return (
            "Medium",
            f"Good match ({top_score:.0%} relevance). "
            "The answer draws on course concepts with high alignment.",
        )
    return (
        "Low",
        f"Partial match ({top_score:.0%} relevance). "
        "The answer is synthesized from limited classroom context.",
    )


def _why_text(score: float, snippet: str) -> str:
    clipped = snippet[:60].replace("\n", " ")
    if score >= _HIGH_THRESHOLD:
        return f'Strong semantic match: "{clipped}…"'
    if score >= _MEDIUM_THRESHOLD:
        return f'Partial match: "{clipped}…"'
    return f'Weak match included for context: "{clipped}…"'


# ── Public API ───────────────────────────────────────────────────────────────

def build_explainability(
    query: str,  # noqa: ARG001  (reserved for future query-aware explanations)
    reranked_children: list[Document],
    parent_docs: list[dict],
    top_score: float,
    retrieval_label: str,
) -> dict:
    """
    Build the explainability payload sent to the frontend.

    Parameters
    ----------
    query:
        Original student question (reserved for future use).
    reranked_children:
        Top-N child chunk Documents after cross-encoder reranking.
        Each should have ``metadata["relevance_score"]`` set.
    parent_docs:
        Corresponding parent chunk dicts (same order as reranked_children).
    top_score:
        Highest reranker logit from the reranking step.
    retrieval_label:
        One of ``CLASSROOM_GROUNDED``, ``CLASSROOM_LOW_CONFIDENCE``,
        ``CLASSROOM_INSUFFICIENT``.

    Returns
    -------
    dict with keys::

        {
            "confidence_label":  "High" | "Medium" | "Low",
            "confidence_score":  float,            # top reranker score (0-1)
            "retrieval_label":   str,
            "narrative":         str,              # human-readable explanation
            "per_source": [
                {
                    "index":          int,         # 1-indexed citation ref
                    "title":          str,
                    "content_type":   str,
                    "alternate_link": str,
                    "score":          float,
                    "score_pct":      str,         # e.g. "72%"
                    "why":            str,
                }
            ]
        }
    """
    confidence_label, narrative = _confidence_label_and_narrative(
        top_score, retrieval_label
    )

    per_source: list[dict] = []
    for i, child in enumerate(reranked_children):
        score = float(child.metadata.get("relevance_score", 0.0))

        # Best-effort metadata from the parent doc (richer than child metadata)
        parent = parent_docs[i] if i < len(parent_docs) else {}
        parent_meta = parent.get("metadata", {}) if isinstance(parent, dict) else {}

        child_meta = child.metadata or {}
        title = (
            parent_meta.get("title")
            or child_meta.get("title")
            or "Unknown source"
        )
        content_type = (
            parent_meta.get("content_type")
            or child_meta.get("content_type")
            or "unknown"
        )
        alternate_link = (
            parent_meta.get("alternate_link")
            or child_meta.get("alternate_link")
            or "#"
        )

        per_source.append(
            {
                "index":          i + 1,
                "title":          title,
                "content_type":   content_type,
                "alternate_link": alternate_link,
                "score":          round(score, 4),
                "score_pct":      f"{min(score * 100, 99):.0f}%",
                "why":            _why_text(score, child.page_content),
            }
        )

    return {
        "confidence_label":  confidence_label,
        "confidence_score":  round(top_score, 4),
        "retrieval_label":   retrieval_label,
        "narrative":         narrative,
        "per_source":        per_source,
    }
