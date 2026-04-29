"""
app/retrieval/retriever.py
──────────────────────────
Hybrid Retrieval Pipeline.
"""
import asyncio
import logging
from typing import Any

from langchain_community.document_compressors.flashrank_rerank import FlashrankRerank
from langchain_core.documents import Document
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import MongoClient
from app.db.vector_repository import get_vector_repository

from app.config import Settings, get_settings
from app.db.semantic_cache_repository import SemanticCacheRepository
from app.retrieval.parent_fetch import fetch_parents

logger = logging.getLogger(__name__)

def deduplicate_docs(docs: list[Document]) -> list[Document]:
    """Remove duplicate Documents by page_content fingerprint."""
    from hashlib import sha256
    seen: set[str] = set()
    unique: list[Document] = []
    for doc in docs:
        fingerprint = sha256(doc.page_content.encode("utf-8")).hexdigest()
        if fingerprint not in seen:
            seen.add(fingerprint)
            unique.append(doc)
    return unique


def reciprocal_rank_fusion(
    results: list[list[Document]], k: int = 60
) -> list[Document]:
    """Merges multiple retrieval lists using Reciprocal Rank Fusion."""
    fused_scores: dict[str, float] = {}
    doc_map: dict[str, Document] = {}

    for doc_list in results:
        for rank, doc in enumerate(doc_list):
            doc_id = f"{doc.page_content}_{doc.metadata.get('source', '')}"
            if doc_id not in doc_map:
                doc_map[doc_id] = doc

            fused_scores[doc_id] = fused_scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)

    sorted_ids = sorted(fused_scores.keys(), key=lambda x: fused_scores[x], reverse=True)
    return [doc_map[did] for did in sorted_ids]


async def get_hybrid_docs(
    query: str,
    user_id: str,
    course_id: str,
    sync_client: MongoClient,
    db: AsyncIOMotorDatabase,
    settings: Settings,
    document_type: str | None = None,
    k: int = 20
) -> list[Document]:
    """Executes parallel local searches and fuses them."""
    repo = get_vector_repository()
    vector_store = repo.get_vector_store(sync_client)
    
    pre_filter = {"user_id": user_id, "course_id": course_id}
    if document_type:
        pre_filter["metadata.source"] = document_type
    
    vector_task = asyncio.to_thread(
        vector_store.similarity_search,
        query,
        k=k,
        pre_filter=pre_filter
    )
    
    async def lexical_search():
        coll = db[settings.mongo_child_chunks_collection]
        cursor = coll.find(
            {"$text": {"$search": query}, **pre_filter},
            {"score": {"$meta": "textScore"}}
        ).sort([("score", {"$meta": "textScore"})]).limit(k)
        
        docs = []
        async for item in cursor:
            docs.append(Document(
                page_content=item["content"],
                metadata=item.get("metadata", {})
            ))
        return docs

    vector_results, keyword_results = await asyncio.gather(
        vector_task,
        lexical_search()
    )
    
    return reciprocal_rank_fusion([vector_results, keyword_results])


def get_retrieval_chain(
    user_id: str,
    course_id: str,
    db: AsyncIOMotorDatabase,
    sync_client: MongoClient,
    settings: Settings,
    document_type: str | None = None,
):
    """Returns a local-first retrieval chain with semantic caching."""
    from langchain_core.runnables import RunnableLambda

    cache = SemanticCacheRepository(db)
    repo = get_vector_repository()
    embeddings = repo.get_embeddings()

    compressor = FlashrankRerank(
        model=settings.local_reranker_model,
        top_n=settings.reranker_top_n,
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
        docs = await get_hybrid_docs(query, user_id, course_id, sync_client, db, settings, document_type=document_type)
        reranked = await asyncio.to_thread(compressor.compress_documents, docs, query)
        parents = await fetch_parents(reranked, user_id, course_id, db, settings)
        
        result = {
            "documents": parents,
            "top_score": max([d.metadata.get("relevance_score", 0.0) for d in reranked]) if reranked else 0.0,
            "child_count": len(reranked),
            "raw_docs": [
                {"page_content": d.page_content, "metadata": d.metadata} 
                for d in reranked
            ] # Serialized for cache
        }

        # ── 3. Background Cache Save ──────────────────────────────────────────
        asyncio.create_task(cache.save_context(user_id, course_id, query, query_vector, result))
        
        return result

    return RunnableLambda(retrieval_logic)
