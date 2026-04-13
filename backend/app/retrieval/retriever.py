import logging
from typing import Any

from langchain_cohere import CohereRerank
from langchain.retrievers import ContextualCompressionRetriever
from langchain_core.documents import Document
from langchain_mongodb import MongoDBAtlasVectorSearch
from langchain_mongodb.retrievers import MongoDBAtlasHybridSearchRetriever
from langchain_nomic import NomicEmbeddings
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import MongoClient

from app.config import Settings, get_settings
from app.retrieval.parent_fetch import fetch_parents

logger = logging.getLogger(__name__)


def build_embeddings(settings: Settings) -> NomicEmbeddings:
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


def get_retriever(
    user_id: str,
    course_id: str,
    sync_client: MongoClient,
    settings: Settings | None = None,
    k: int | None = None,
) -> MongoDBAtlasHybridSearchRetriever:
    """
    Return a pre-filtered LangChain Hybrid Retriever for the specified course.
    Combines vector search + BM25 full-text search for superior recall.
    """
    resolved = settings or get_settings()
    k = k or resolved.retrieval_k

    collection = sync_client[resolved.mongo_db_name][
        resolved.mongo_child_chunks_collection
    ]

    vector_store = MongoDBAtlasVectorSearch(
        collection=collection,
        embedding=build_embeddings(resolved),
        index_name=resolved.mongo_child_vector_index_name,
        text_key="content",
    )

    return MongoDBAtlasHybridSearchRetriever(
        vectorstore=vector_store,
        search_index_name=resolved.mongo_child_bm25_index_name,
        top_k=k,
        pre_filter={"user_id": {"$eq": user_id}, "course_id": {"$eq": course_id}},
    )


def get_retrieval_chain(
    user_id: str,
    course_id: str,
    db: AsyncIOMotorDatabase,
    sync_client: MongoClient,
    settings: Settings,
):
    """
    Returns a declarative LangChain Runnable that:
    1. Retrieves candidates via Hybrid Search (Vector + BM25)
    2. Reranks and compresses results via Cohere
    3. Deduplicates results
    4. Fetches parent documents
    5. Serializes to dicts for Graph State
    """
    base_retriever = get_retriever(user_id, course_id, sync_client, settings)

    # Integrated Cohere Reranker (uses settings.reranker_model from .env)
    compressor = CohereRerank(
        cohere_api_key=settings.cohere_api_key,
        model=settings.reranker_model,
        top_n=settings.reranker_top_n
    )

    compression_retriever = ContextualCompressionRetriever(
        base_compressor=compressor,
        base_retriever=base_retriever
    )

    async def fetch_and_serialize(docs: list[Document]) -> dict[str, Any]:
        parents = await fetch_parents(docs, db, settings)
        top_score = 0.0
        if docs:
            top_score = max(float(d.metadata.get("relevance_score", 0.0)) for d in docs)

        return {
            "documents": parents,
            "top_score": top_score,
            "child_count": len(docs),
            "raw_docs": docs  # specifically for explainability building
        }

    # The final pipeline
    return (
        compression_retriever
        | fetch_and_serialize
    )
