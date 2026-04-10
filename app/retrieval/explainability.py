"""
Retrieval explainability — pure Python, zero LLM calls.

Derives a human-readable confidence narrative and per-source breakdown
directly from cross-encoder reranker scores.

Score interpretation
--------------------
The cross-encoder (``ms-marco-MiniLM-L-6-v2``) outputs raw logits.
Empirically:

* logit ≥ 0.65 → Strong semantic match
* 0.35 ≤ logit < 0.65 → Moderate match
* logit < 0.35 → Weak match (web fallback fires)

These thresholds are consistent with the web-fallback trigger in
``fallback.py`` (``TAVILY_THRESHOLD = 0.35``).
"""
from __future__ import annotations

from langchain_core.documents import Document


# ── Confidence thresholds ────────────────────────────────────────────────────

_HIGH_THRESHOLD   = 0.65
_MEDIUM_THRESHOLD = 0.35  # == TAVILY_THRESHOLD


def _confidence_label_and_narrative(
    top_score: float,
    retrieval_label: str,
) -> tuple[str, str]:
    if retrieval_label == "WEB_ONLY":
        return (
            "Low",
            "Weak classroom match. Answer draws primarily on web sources or general knowledge.",
        )
    if top_score >= _HIGH_THRESHOLD:
        return (
            "High",
            f"Strong classroom match ({top_score:.0%} relevance). "
            "Answer is fully grounded in your course materials.",
        )
    if top_score >= _MEDIUM_THRESHOLD:
        return (
            "Medium",
            f"Moderate match ({top_score:.0%} relevance). "
            "Answer draws on classroom content with some interpretation.",
        )
    return (
        "Low",
        "Weak classroom match. Answer supplements course materials with web sources.",
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
        Each should have ``metadata["reranker_score"]`` set.
    parent_docs:
        Corresponding parent chunk dicts (same order as reranked_children).
    top_score:
        Highest reranker logit from the reranking step.
    retrieval_label:
        One of ``CLASSROOM_GROUNDED``, ``CLASSROOM_PARTIAL_WEB``,
        ``WEB_ONLY``.

    Returns
    -------
    dict with keys::

        {
            "confidence_label":  "High" | "Medium" | "Low",
            "confidence_score":  float,            # top reranker logit
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
        score = float(child.metadata.get("reranker_score", 0.0))

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
