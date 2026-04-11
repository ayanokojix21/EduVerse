from __future__ import annotations

from fastapi import Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import Settings, get_settings
from app.db.mongodb import get_db


class SemanticCacheService:
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


def get_semantic_cache_service(
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> SemanticCacheService:
    return SemanticCacheService(db=db)
