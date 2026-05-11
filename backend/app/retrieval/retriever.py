"""
app/retrieval/retriever.py
──────────────────────────
Hybrid Retrieval Pipeline — Cloud Native.

Uses:
  - LangChain MongoDBAtlasHybridSearchRetriever
  - MongoDB Atlas Vector Search (semantic)
  - MongoDB Atlas Search (Lucene / BM25)
  - Cohere Rerank v3.5 (cloud reranker)
"""
import asyncio
import logging
from typing import Any

from langchain_cohere import CohereRerank
from langchain_mongodb.retrievers.hybrid_search import MongoDBAtlasHybridSearchRetriever
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import MongoClient

from app.config import Settings
from app.db.vector_repository import get_vector_repository
from app.db.semantic_cache_repository import SemanticCacheRepository
from app.retrieval.parent_fetch import fetch_parents

logger = logging.getLogger(__name__)


def get_retrieval_chain(
    user_id: str,
    course_id: str,
    db: AsyncIOMotorDatabase,
    sync_client: MongoClient,
    settings: Settings,
    document_type: str | None = None,
):
    """Returns a cloud-native retrieval chain with Cohere reranking and semantic caching."""
    from langchain_core.runnables import RunnableLambda

    cache = SemanticCacheRepository(db)
    repo = get_vector_repository()
    embeddings = repo.get_embeddings()
    vector_store = repo.get_vector_store(sync_client)

    # ── Cohere Cloud Reranker ─────────────────────────────────────────────────
    compressor = CohereRerank(
        cohere_api_key=settings.cohere_api_key,
        model=settings.cohere_reranker_model,
        top_n=settings.reranker_top_n,
    )

    # ── LangChain Hybrid Retriever (Vector + Atlas Search BM25 + RRF) ─────────
    pre_filter = {"user_id": {"$eq": user_id}, "course_id": {"$eq": course_id}}
    if document_type:
        pre_filter["metadata.source"] = {"$eq": document_type}

    hybrid_retriever = MongoDBAtlasHybridSearchRetriever(
        vectorstore=vector_store,
        search_index_name=settings.mongo_child_bm25_index_name,
        top_k=settings.retrieval_k,
        pre_filter=pre_filter,
    )

    async def retrieval_logic(input_data) -> dict[str, Any]:
        if isinstance(input_data, str):
            query = input_data
        else:
            query = input_data.get("query", "")

        # ── 1. Semantic Cache Lookup ──────────────────────────────────────────
        query_vector = await asyncio.to_thread(embeddings.embed_query, query)
        cached_payload = await cache.get_cached_context(user_id, course_id, query_vector)

        if cached_payload:
            return cached_payload

        # ── 2. Cache Miss: Full Retrieval Path ────────────────────────────────
        docs = await hybrid_retriever.ainvoke(query)
        
        if not docs:
            return {
                "documents": [],
                "top_score": 0.0,
                "child_count": 0,
                "raw_docs": []
            }

        try:
            reranked = await asyncio.to_thread(compressor.compress_documents, docs, query)
        except Exception as e:
            logger.warning(f"Cohere reranker failed: {e}. Falling back to un-reranked hybrid results.")
            for i, d in enumerate(docs[:settings.reranker_top_n]):
                d.metadata["relevance_score"] = 0.99 - (i * 0.01)
            reranked = docs[:settings.reranker_top_n]

        parents = await fetch_parents(reranked, user_id, course_id, db, settings)

        result = {
            "documents": parents,
            "top_score": max([d.metadata.get("relevance_score", 0.0) for d in reranked]) if reranked else 0.0,
            "child_count": len(reranked),
            "raw_docs": [
                {"page_content": d.page_content, "metadata": d.metadata}
                for d in reranked
            ],
        }

        # ── 3. Background Cache Save ──────────────────────────────────────────
        asyncio.create_task(cache.save_context(user_id, course_id, query, query_vector, result))

        return result

    return RunnableLambda(retrieval_logic)

