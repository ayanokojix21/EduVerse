"""
Cross-encoder reranker using FlashRank (ONNX-based, no PyTorch required).

FlashRank ships with the ``ms-marco-MiniLM-L-6-v2`` model by default and
runs inference via ONNX Runtime — orders of magnitude lighter than
``sentence-transformers`` + PyTorch (~10 MB vs ~2 GB).

API
---
``rerank(query, docs, top_n)`` is **synchronous** — call it inside
``anyio.to_thread.run_sync`` from async contexts.

``warm_up_reranker()`` pre-loads the ONNX model during startup so the
first real request has zero cold-start penalty.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import anyio
from langchain_core.documents import Document

from app.config import Settings, get_settings

if TYPE_CHECKING:
    from flashrank import Ranker

logger = logging.getLogger(__name__)

_ranker: "Ranker | None" = None


def _get_ranker(settings: Settings) -> "Ranker":
    """Return (and lazily create) the FlashRank singleton."""
    global _ranker  # noqa: PLW0603
    if _ranker is None:
        from flashrank import Ranker  # type: ignore[import-untyped]
        logger.info("Loading FlashRank model: %s", settings.reranker_model)
        # FlashRank accepts the HuggingFace model name directly.
        _ranker = Ranker(model_name=settings.reranker_model, cache_dir="/tmp/flashrank")
        logger.info("FlashRank reranker ready.")
    return _ranker


async def warm_up_reranker(settings: Settings | None = None) -> None:
    """
    Pre-load the ONNX reranker model in a thread pool.
    Called during FastAPI lifespan startup.
    """
    resolved = settings or get_settings()
    await anyio.to_thread.run_sync(_get_ranker, resolved)


def rerank(
    query: str,
    docs: list[Document],
    top_n: int | None = None,
    settings: Settings | None = None,
) -> tuple[list[Document], float]:
    """
    Rerank *docs* against *query* using FlashRank cross-encoder.

    This is a **synchronous** function — wrap in ``anyio.to_thread.run_sync``
    when called from async code.

    Parameters
    ----------
    query:
        The original student question.
    docs:
        Candidate Documents from hybrid search (typically top-20).
    top_n:
        Number of top results to return. Defaults to ``settings.reranker_top_n``.

    Returns
    -------
    ``(reranked_docs[:top_n], top_score)``

    Each returned Document has ``metadata["reranker_score"]`` set to its
    FlashRank relevance score (higher = more relevant).
    """
    from flashrank import RerankRequest  # type: ignore[import-untyped]

    resolved = settings or get_settings()
    top_n = top_n or resolved.reranker_top_n

    if not docs:
        return [], 0.0

    ranker = _get_ranker(resolved)

    # FlashRank expects a list of dicts with an "id" and "text" key.
    passages = [
        {"id": i, "text": doc.page_content}
        for i, doc in enumerate(docs)
    ]
    request = RerankRequest(query=query, passages=passages)
    results = ranker.rerank(request)

    # ``results`` is a list of dicts: {"id": int, "score": float, "text": str}
    # sorted descending by score.
    scored_docs: list[tuple[float, Document]] = []
    for result in results:
        idx = result["id"]
        score = float(result["score"])
        doc = docs[idx]
        doc.metadata["reranker_score"] = score
        scored_docs.append((score, doc))

    scored_docs.sort(key=lambda x: x[0], reverse=True)
    top_score = scored_docs[0][0] if scored_docs else 0.0
    reranked = [doc for _, doc in scored_docs[:top_n]]

    return reranked, top_score
