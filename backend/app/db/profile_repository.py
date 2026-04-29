from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import Settings, get_settings
from app.db.mongodb import get_db
from app.schemas.db import StudentProfile


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

class ProfileRepository:
    """
    Data Access Layer for Student Profiles.
    Encapsulates all MongoDB logic for user metadata and pedagogical tracking.
    """
    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.collection = db[self.settings.mongo_user_profiles_collection]

    async def get_profile(self, user_id: str) -> StudentProfile:
        """Retrieves a typed student profile or initializes a new one atomically."""
        doc = await self.collection.find_one({"user_id": user_id})
        if doc is None:
            profile = StudentProfile(user_id=user_id)
            await self.collection.insert_one(profile.model_dump())
            return profile
        return StudentProfile(**doc)

    async def get_weak_topics(self, user_id: str) -> list[str]:
        """Retrieves knowledge gaps for retrieval grounding."""
        doc = await self.collection.find_one(
            {"user_id": user_id},
            projection={"weak_topics": 1},
        )
        return list(doc.get("weak_topics", [])) if doc else []

    async def update_topic_mastery(self, user_id: str, topic: str, delta: float) -> None:
        """
        Updates mastery level for a specific topic using a probabilistic clamp.
        delta: positive for improvement, negative for decline.
        """
        profile = await self.get_profile(user_id)
        current = profile.topic_mastery.get(topic, 0.5)

        new_score = max(0.0, min(1.0, current + delta))
        
        await self.collection.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    f"topic_mastery.{topic}": new_score,
                    "updated_at": _utc_now(),
                },
                "$setOnInsert": {"session_count": 0, "weak_topics": []},
            },
            upsert=True,
        )

    async def update_weak_topics(self, user_id: str, new_topics: list[str]) -> None:
        """Persists identified knowledge gaps with ordering and uniqueness constraints."""
        doc = await self.collection.find_one({"user_id": user_id}, projection={"weak_topics": 1})
        existing = list(doc.get("weak_topics", [])) if doc else []
        merged = list(dict.fromkeys(existing + new_topics))[:20] 
        await self.collection.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "weak_topics": merged,
                    "updated_at": _utc_now(),
                },
                "$setOnInsert": {"session_count": 0},
            },
            upsert=True,
        )

    async def increment_session(self, user_id: str) -> int:
        """Atomic increment of human-AI interaction sessions."""
        result = await self.collection.find_one_and_update(
            {"user_id": user_id},
            {
                "$inc": {"session_count": 1},
                "$set": {"updated_at": _utc_now()},
                "$setOnInsert": {"weak_topics": []},
            },
            upsert=True,
            return_document=True,
        )
        return int(result["session_count"])

def get_profile_repository(
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> ProfileRepository:
    return ProfileRepository(db=db)


__all__ = ["ProfileRepository", "get_profile_repository"]
