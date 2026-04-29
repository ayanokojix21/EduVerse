from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import Settings, get_settings
from app.db.mongodb import get_db


class SemanticCacheRepository:
    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.collection = db[self.settings.mongo_semantic_cache_collection]

    async def clear_course_cache(self, user_id: str, course_id: str) -> int:
        result = await self.collection.delete_many({
            "user_id": user_id,
            "course_id": course_id,
        })
        return int(result.deleted_count)

    async def get_cached_context(
        self, 
        user_id: str, 
        course_id: str, 
        query_vector: List[float],
        threshold: float = 0.96
    ) -> Optional[Dict[str, Any]]:
        try:
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": self.settings.mongo_semantic_cache_vector_index_name, 
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
                        "payload": 1
                    }
                }
            ]
            
            async for doc in self.collection.aggregate(pipeline):
                if doc.get("score", 0) >= threshold:
                    return doc.get("payload")
                
            return None
        except Exception:
            return None

    async def save_context(
        self, 
        user_id: str, 
        course_id: str, 
        query: str, 
        query_vector: List[float], 
        payload: Dict[str, Any]
    ) -> None:
        try:
            cache_entry = {
                "user_id": user_id,
                "course_id": course_id,
                "query": query,
                "query_vector": query_vector,
                "payload": payload,
                "created_at": datetime.now(timezone.utc)
            }
            await self.collection.insert_one(cache_entry)
        except Exception:
            pass


def get_semantic_cache_repository(
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> SemanticCacheRepository:
    return SemanticCacheRepository(db=db)
