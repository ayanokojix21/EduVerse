"""
Node 3 — RAG Agent  (no LLM — pure retrieval + explainability)

Runs the complete retrieval pipeline for both rewritten queries in parallel,
then merges, reranks, fetches parent chunks, optionally falls back to web
search, and produces a zero-LLM explainability payload.

Pipeline
--------
1.  Check semantic cache (short-circuit if HIT) *[not yet implemented — placeholder]*
2.  Parallel hybrid search on both rewritten queries (asyncio.gather)
3.  Deduplicate merged child-chunk results
4.  Cross-encoder reranking (FlashRank, runs in thread pool)
5.  Parent chunk fetch  (single MongoDB $in)
6.  Web fallback if top reranker score < threshold
7.  Build explainability (pure Python, zero LLM)

Context docs passed to tutors are serialisable dicts (no LangChain Documents),
so they work cleanly across Send API state boundaries and JSON serialisation.

LangChain / LangGraph best-practices
--------------------------------------
* ``anyio.to_thread.run_sync`` keeps CPU-bound reranker off the event loop.
* ``asyncio.gather`` parallelises both retrieval queries.
* ``@traceable`` creates a named LangSmith span.
"""
from __future__ import annotations

import asyncio
import logging
import time

import anyio
from langchain_core.runnables import RunnableConfig
from langsmith import traceable
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.agents.state import AgentState
from app.config import get_settings
from app.retrieval.explainability import build_explainability
from app.retrieval.fallback import apply_web_fallback
from app.retrieval.parent_fetch import fetch_parents
from app.retrieval.reranker import rerank
from app.retrieval.retriever import deduplicate_docs, hybrid_search

logger = logging.getLogger(__name__)
settings = get_settings()


def _docs_to_dicts(docs) -> list[dict]:
    """Convert LangChain Documents to plain, JSON-serialisable dicts."""
    result = []
    for doc in docs:
        result.append(
            {
                "content": doc.page_content,
                "metadata": dict(doc.metadata),
                # promote common metadata fields for easy template access
                "parent_id": doc.metadata.get("parent_id", ""),
                "reranker_score": float(doc.metadata.get("reranker_score", 0.0)),
            }
        )
    return result


@traceable(name="rag_agent")
async def rag_agent_node(state: AgentState, config: RunnableConfig) -> dict:
    """
    Execute the full retrieval pipeline.

    Requires ``db`` to be injected into runtime config via
    ``config["configurable"]["db"]`` (set by the chat endpoint).
    """
    t0 = time.monotonic()

    db: AsyncIOMotorDatabase = config["configurable"]["db"]
    user_id: str = state["user_id"]
    course_id: str = state["course_id"]
    original_query: str = state["original_query"]
    rewritten_queries: list[str] = state.get("rewritten_queries") or [original_query]

    # ── 1. Parallel hybrid search on both rewritten queries ───────────────────
    search_tasks = [
        hybrid_search(q, user_id, course_id, db, settings)
        for q in rewritten_queries
    ]
    results = await asyncio.gather(*search_tasks, return_exceptions=True)

    raw_docs = []
    for r in results:
        if isinstance(r, Exception):
            logger.warning("Hybrid search failed for a query: %s", r)
        else:
            raw_docs.extend(r)

    child_docs = deduplicate_docs(raw_docs)
    logger.info("RAG agent → %d unique child docs after dedup", len(child_docs))

    # ── 2. Cross-encoder reranking (FlashRank — synchronous, run in thread) ──
    reranked_children, top_score = await anyio.to_thread.run_sync(
        lambda: rerank(original_query, child_docs, settings=settings)
    )
    logger.info(
        "Reranker → top_score=%.3f, keeping top %d/%d docs",
        top_score,
        len(reranked_children),
        len(child_docs),
    )

    # ── 3. Parent chunk fetch ─────────────────────────────────────────────────
    parent_docs = await fetch_parents(reranked_children, db, settings)
    logger.info("Parent fetch → %d parent chunks", len(parent_docs))

    # ── 4. Web fallback (fires only if top_score < tavily_threshold) ──────────
    web_docs, retrieval_label = await apply_web_fallback(
        original_query, top_score, db, settings
    )
    if web_docs:
        logger.info(
            "Web fallback → %d docs added (%s)", len(web_docs), retrieval_label
        )

    # ── 5. Build context_docs for tutors ─────────────────────────────────────
    # Parent docs (dicts from MongoDB) + web docs (already dicts)
    context_docs: list[dict] = parent_docs + web_docs

    # ── 6. Explainability (pure Python) ──────────────────────────────────────
    explainability = build_explainability(
        query=original_query,
        reranked_children=reranked_children,
        parent_docs=parent_docs,
        top_score=top_score,
        retrieval_label=retrieval_label,
    )

    retrieval_ms = int((time.monotonic() - t0) * 1000)
    confidence_label = explainability.get("confidence_label", "Low")

    logger.info(
        "RAG agent done → %s · %s · %.0f%% · %dms",
        retrieval_label,
        confidence_label,
        top_score * 100,
        retrieval_ms,
    )

    return {
        "context_docs": context_docs,
        "retrieval_label": retrieval_label,
        "top_reranker_score": top_score,
        "retrieval_ms": retrieval_ms,
        "explainability": explainability,
        "agent_thoughts": [
            {
                "node": "rag_agent",
                "summary": (
                    f"{len(parent_docs)} parent chunks · {retrieval_label} · "
                    f"{confidence_label} confidence · {retrieval_ms}ms"
                ),
                "data": {
                    "parent_count": len(parent_docs),
                    "web_count": len(web_docs),
                    "retrieval_label": retrieval_label,
                    "confidence_label": confidence_label,
                    "confidence_score": round(top_score, 4),
                    "retrieval_ms": retrieval_ms,
                },
            }
        ],
    }
