"""
Hybrid retriever — MongoDB Atlas vector search + BM25 text search,
merged with Reciprocal Rank Fusion (RRF).

Architecture
------------
Instead of raw PyMongo aggregation pipelines, we utilize LangChain MongoDB's
native `MongoDBAtlasHybridSearchRetriever`. It provides out-of-the-box support for:
1. Vector Search + Text Search execution.
2. Reciprocal Rank Fusion blending logic.
3. Pre-filtering by arbitrary fields (user_id and course_id).
"""
from __future__ import annotations

import logging

import anyio
from langchain_core.documents import Document
from langchain_mongodb.retrievers.hybrid_search import MongoDBAtlasHybridSearchRetriever
from langchain_mongodb.vectorstores import MongoDBAtlasVectorSearch
from langchain_nomic import NomicEmbeddings
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import MongoClient

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


def _build_embeddings(settings: Settings) -> NomicEmbeddings:
    return NomicEmbeddings(
        model=settings.nomic_embedding_model,
        nomic_api_key=settings.nomic_api_key,
    )


def deduplicate_docs(docs: list[Document]) -> list[Document]:
    """
    Remove duplicate Documents by page_content fingerprint.
    Preserves the first occurrence (highest-ranked) of each unique passage.
    """
    seen: set[str] = set()
    unique: list[Document] = []
    for doc in docs:
        key = doc.page_content[:100]
        if key not in seen:
            seen.add(key)
            unique.append(doc)
    return unique


async def hybrid_search(
    query: str,
    user_id: str,
    course_id: str,
    db: AsyncIOMotorDatabase,
    settings: Settings | None = None,
    k: int | None = None,
) -> list[Document]:
    """
    Perform native LangChain MongoDB hybrid search (vector + BM25) and return 
    the top-k deduplicated `Document` objects ranked by RRF score.
    """
    resolved = settings or get_settings()
    k = k or resolved.retrieval_k

    def _run_hybrid_sync() -> list[Document]:
        # MongoDBAtlasHybridSearchRetriever requires a synchronous pymongo collection.
        # We instantiate a transient sync client per request for retrieval.
        sync_client = MongoClient(resolved.mongo_uri, serverSelectionTimeoutMS=10000)
        try:
            collection = sync_client[resolved.mongo_db_name][
                resolved.mongo_child_chunks_collection
            ]

            vector_store = MongoDBAtlasVectorSearch(
                collection=collection,
                embedding=_build_embeddings(resolved),
                index_name=resolved.mongo_child_vector_index_name,
                text_key="content",
            )

            retriever = MongoDBAtlasHybridSearchRetriever(
                vectorstore=vector_store,
                search_index_name=resolved.mongo_child_bm25_index_name,
                top_k=k,
                pre_filter={"user_id": {"$eq": user_id}, "course_id": {"$eq": course_id}},
            )

            # LangChain's hybrid retriever merges metadata natively, but 
            # nested attributes might need manual promotion depending on version
            docs = retriever.invoke(query)
            
            # Ensure custom metadata requirements from rest of pipe are met
            for doc in docs:
                if doc.metadata:
                    doc.metadata["parent_id"] = doc.metadata.get("parent_id", "")
            return docs
        except Exception as exc:
            logger.error("Hybrid Search failed: %s", exc)
            return []
        finally:
            sync_client.close()

    raw_docs = await anyio.to_thread.run_sync(_run_hybrid_sync)
    return deduplicate_docs(raw_docs)
