"""
Semantic Context Cache (MongoDB Atlas Sector Search)

Caches expensive retrieval results (reranked docs) based on query similarity.
If a new query is >96% similar to a previous one in the same course,
we reuse the 'context_docs', saving ~1.5s of search/rerank time.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional

from langchain_core.documents import Document
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import MongoClient

from app.config import get_settings

logger = logging.getLogger(__name__)

class ContextCache:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.settings = get_settings()
        self.collection_name = "semantic_context_cache"

    async def get_cached_context(
        self, 
        user_id: str, 
        course_id: str, 
        query_vector: List[float],
        threshold: float = 0.96
    ) -> Optional[List[dict]]:
        """
        Check for an existing context in the same course that is 
        semantically very similar to the current query.
        """
        try:
            # We use a raw MongoDB aggregation for vector search to find 
            # the closest match within the same course.
            # NOTE: This requires a search index on the 'query_vector' field.
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": "vector_index", # standard name
                        "path": "query_vector",
                        "queryVector": query_vector,
                        "numCandidates": 10,
                        "limit": 1,
                        "filter": {
                            "course_id": {"$eq": course_id},
                            "user_id": {"$eq": user_id}
                        }
                    }
                },
                {
                    "$project": {
                        "score": {"$meta": "vectorSearchScore"},
                        "context_docs": 1
                    }
                }
            ]
            
            async for doc in self.db[self.collection_name].aggregate(pipeline):
                if doc.get("score", 0) >= threshold:
                    logger.info(f"Context Cache HIT (score: {doc['score']:.4f})")
                    return doc.get("context_docs")
                
            return None
        except Exception as exc:
            logger.warning(f"Context Cache Lookup failed: {exc}")
            return None

    async def save_context(
        self, 
        user_id: str, 
        course_id: str, 
        query: str, 
        query_vector: List[float], 
        context_docs: List[dict]
    ) -> None:
        """Store the retrieval results for future reuse."""
        try:
            # We only store the serializable dicts, not LangChain objects
            cache_entry = {
                "user_id": user_id,
                "course_id": course_id,
                "query": query,
                "query_vector": query_vector,
                "context_docs": context_docs,
                "created_at": datetime.utcnow()
            }
            await self.db[self.collection_name].insert_one(cache_entry)
            logger.info("Context Cache SAVED.")
        except Exception as exc:
            logger.warning(f"Failed to save context to cache: {exc}")
