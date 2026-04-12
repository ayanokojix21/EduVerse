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

from app.retrieval.parent_fetch import fetch_parents
from app.retrieval.reranker import rerank
from app.retrieval.retriever import deduplicate_docs, hybrid_search
from app.utils.llm_pool import RoundRobinLLM

logger = logging.getLogger(__name__)
settings = get_settings()

# Threshold for triggering Map-Reduce distillation
MAX_RAW_CHUNKS = 10
_distiller_llm = RoundRobinLLM.for_role("fast", temperature=0.0)

async def _distill_batch(query: str, batch: list[dict], config: RunnableConfig) -> str:
    """Distill a batch of chunks into relevant facts for the query."""
    context_blob = "\n\n".join([f"--- Chunk ---\n{d['content']}" for d in batch])
    prompt = (
        f"You are a Context Distiller. Below are several chunks from a course document.\n\n"
        f"STUDENT QUERY: {query}\n\n"
        f"COURSE CHUNKS:\n{context_blob}\n\n"
        f"INSTRUCTION:\n"
        f"1. Identify all specific facts, formulas, definitions, and details relevant to the query.\n"
        f"2. Summarize them into a concise, high-density note.\n"
        f"3. If nothing is relevant, return 'NO_RELEVANT_INFO'.\n"
        f"4. Be objective. Do not answer the question, just extract the evidence."
    )
    res = await _distiller_llm.ainvoke([("user", prompt)], config=config)
    return res.content.strip()


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

    # ── 3.5 Context Distillation (Map-Reduce) ─────────────────────────────────
    # If the retrieved context is too large, we distill it in batches.
    is_distilled = False
    if len(parent_docs) > MAX_RAW_CHUNKS:
        logger.info("Large context detected (%d chunks) -> Triggering Map-Reduce distillation", len(parent_docs))
        batch_size = 8
        batches = [parent_docs[i:i + batch_size] for i in range(0, len(parent_docs), batch_size)]
        
        distill_tasks = [_distill_batch(original_query, b, config) for b in batches]
        results = await asyncio.gather(*distill_tasks)
        
        distilled_docs = []
        for i, res in enumerate(results):
            if res and res != "NO_RELEVANT_INFO":
                # Create a synthetic doc for the distilled content
                # We inherit metadata from the first doc in the batch for citation context
                base_meta = batches[i][0].get("metadata", {}).copy()
                base_meta["is_distilled"] = True
                base_meta["title"] = f"Distilled Notes: {base_meta.get('title', 'Course Material')}"
                
                distilled_docs.append({
                    "content": res,
                    "metadata": base_meta,
                    "parent_id": f"distilled-{i}-{int(time.time())}",
                    "reranker_score": 1.0 # Distilled content is highly curated
                })
        
        if distilled_docs:
            parent_docs = distilled_docs
            is_distilled = True
            logger.info("Distillation complete -> %d consolidated context notes", len(parent_docs))
        else:
            logger.warning("Distillation produced no results, falling back to top matched chunks only")
            parent_docs = parent_docs[:MAX_RAW_CHUNKS]

    # ── 4. Retrieval label (NO web fallback — strict classroom grounding) ───
    # We intentionally do NOT fetch web results. The tutors are strictly
    # grounded to course materials only. The label indicates confidence level.
    if top_score >= settings.tavily_threshold:
        retrieval_label = "CLASSROOM_GROUNDED"
    elif top_score >= 0.10:
        retrieval_label = "CLASSROOM_LOW_CONFIDENCE"
    else:
        retrieval_label = "CLASSROOM_INSUFFICIENT"
    web_docs: list = []

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
                    f"{len(parent_docs)} {'distilled' if is_distilled else 'parent'} chunks · {retrieval_label} · "
                    f"{confidence_label} confidence · {retrieval_ms}ms"
                ),
                "data": {
                    "parent_count": len(parent_docs),
                    "is_distilled": is_distilled,
                    "web_count": len(web_docs),
                    "retrieval_label": retrieval_label,
                    "confidence_label": confidence_label,
                    "confidence_score": round(top_score, 4),
                    "retrieval_ms": retrieval_ms,
                },
            }
        ],
    }
