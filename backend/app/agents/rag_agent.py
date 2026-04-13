"""
Node 3 — RAG Agent
Runs the complete retrieval pipeline using MongoDB Vector Search and Cohere Rerank.
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
from app.retrieval.context_cache import ContextCache
from app.retrieval.explainability import build_explainability
from app.retrieval.retriever import build_embeddings, get_retrieval_chain
from app.utils.llm_pool import RoundRobinLLM

logger = logging.getLogger(__name__)
settings = get_settings()

# Threshold for triggering Map-Reduce distillation
MAX_RAW_CHUNKS = 20
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


@traceable(name="rag_agent")
async def rag_agent_node(state: AgentState, config: RunnableConfig) -> dict:
    """
    Execute the full retrieval pipeline with Context Caching and 
    LangChain Contextual Compression.
    """
    t0 = time.monotonic()

    db: AsyncIOMotorDatabase = config["configurable"]["db"]
    user_id: str = state["user_id"]
    course_id: str = state["course_id"]
    original_query: str = state["original_query"]
    rewritten_queries: list[str] = state.get("rewritten_queries") or [original_query]
    
    cache = ContextCache(db)
    embeddings = build_embeddings(settings)
    
    # ── 0. Check Semantic Context Cache ──────────────────────────────────────
    try:
        query_vector = await anyio.to_thread.run_sync(
            lambda: embeddings.embed_query(original_query)
        )
        cached_docs = await cache.get_cached_context(user_id, course_id, query_vector)
        if cached_docs:
            retrieval_ms = int((time.monotonic() - t0) * 1000)
            return {
                "context_docs": cached_docs,
                "retrieval_label": "CACHED_CONTEXT",
                "top_reranker_score": 1.0,
                "retrieval_ms": retrieval_ms,
                "agent_thoughts": [
                    {
                        "node": "rag_agent",
                        "summary": f"Context Cache HIT · Reusing {len(cached_docs)} documents · {retrieval_ms}ms",
                        "data": {
                            "is_cached": True,
                            "parent_count": len(cached_docs),
                            "retrieval_ms": retrieval_ms,
                        },
                    }
                ],
            }
    except Exception as e:
        logger.warning(f"Cache embedding check failed or miss: {e}")
        query_vector = None

    # ── 1. Execute Declarative Retrieval Chain ───────────────────────────────
    chain = get_retrieval_chain(user_id, course_id, db, settings)
    
    retrieval_result = await chain.ainvoke(rewritten_queries, config=config)
    
    parent_docs = retrieval_result["documents"]
    top_score = retrieval_result["top_score"]
    reranked_children = retrieval_result["raw_docs"]

    logger.info(
        "Modernized Reranker → top_score=%.3f, keeping %d documents across %d queries",
        top_score, len(parent_docs), len(rewritten_queries)
    )

    # ── 2. Context Distillation (Map-Reduce) ─────────────────────────────────
    is_distilled = False
    if parent_docs and len(parent_docs) > MAX_RAW_CHUNKS:
        logger.info("Large context detected (%d chunks) -> Triggering Map-Reduce distillation", len(parent_docs))
        batch_size = 8
        batches = [parent_docs[i:i + batch_size] for i in range(0, len(parent_docs), batch_size)]
        
        distill_tasks = [_distill_batch(original_query, b, config) for b in batches]
        distill_results = await asyncio.gather(*distill_tasks)
        
        distilled_docs = []
        for i, res in enumerate(distill_results):
            if res and res != "NO_RELEVANT_INFO":
                base_meta = batches[i][0].get("metadata", {}).copy()
                base_meta["is_distilled"] = True
                base_meta["title"] = f"Distilled Notes: {base_meta.get('title', 'Course Material')}"
                distilled_docs.append({
                    "content": res,
                    "metadata": base_meta,
                    "parent_id": f"distilled-{i}-{int(time.time())}",
                    "reranker_score": 1.0
                })
        
        if distilled_docs:
            parent_docs = distilled_docs
            is_distilled = True
            logger.info("Distillation complete -> %d consolidated context notes", len(parent_docs))
        else:
            parent_docs = parent_docs[:MAX_RAW_CHUNKS]

    # ── 3. Final Processing & Labeling ──────────────────────────────────────
    if top_score >= 0.70:
        retrieval_label = "CLASSROOM_GROUNDED"
    elif top_score >= 0.40:
        retrieval_label = "CLASSROOM_LOW_CONFIDENCE"
    else:
        retrieval_label = "CLASSROOM_INSUFFICIENT"

    context_docs: list[dict] = parent_docs

    # ── 4. Cache / Explain / Return ──────────────────────────────────────────
    if query_vector and context_docs and retrieval_label != "CLASSROOM_INSUFFICIENT":
        await cache.save_context(user_id, course_id, original_query, query_vector, context_docs)

    explainability = build_explainability(
        query=original_query,
        reranked_children=reranked_children,
        parent_docs=parent_docs,
        top_score=top_score,
        retrieval_label=retrieval_label,
    )

    retrieval_ms = int((time.monotonic() - t0) * 1000)
    confidence_label = explainability.get("confidence_label", "Low")

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
                    "is_cached": False,
                    "parent_count": len(parent_docs),
                    "is_distilled": is_distilled,
                    "retrieval_label": retrieval_label,
                    "confidence_score": round(top_score, 4),
                    "retrieval_ms": retrieval_ms,
                },
            }
        ],
    }
