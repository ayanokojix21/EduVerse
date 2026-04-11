from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import Settings, get_settings
from app.db.mongodb import get_db


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ProfileStore:
    """
    Stores per-user adaptive-learning state in MongoDB ``user_profiles``
    collection.

    Schema::

        {
            "user_id":       str,         # unique key (Google sub)
            "weak_topics":   list[str],   # detected knowledge gaps
            "session_count": int,         # total chat sessions
            "updated_at":    datetime,
        }
    """

    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.collection = db[self.settings.mongo_user_profiles_collection]

    async def get_profile(self, user_id: str) -> dict[str, Any]:
        """Return the full profile dict.  Creates one if it doesn't exist."""
        doc = await self.collection.find_one({"user_id": user_id})
        if doc is None:
            doc = {
                "user_id": user_id,
                "weak_topics": [],
                "session_count": 0,
                "updated_at": _utc_now(),
            }
            await self.collection.insert_one(doc)
        return {
            "user_id": user_id,
            "weak_topics": doc.get("weak_topics", []),
            "session_count": doc.get("session_count", 0),
        }

    async def get_weak_topics(self, user_id: str) -> list[str]:
        doc = await self.collection.find_one(
            {"user_id": user_id},
            projection={"weak_topics": 1},
        )
        if doc is None:
            return []
        return list(doc.get("weak_topics", []))

    async def update_weak_topics(self, user_id: str, new_topics: list[str]) -> None:
        """
        Merge ``new_topics`` into the stored list, cap at 20 unique entries,
        and persist the update.
        """
        existing = await self.get_weak_topics(user_id)
        merged = list(dict.fromkeys(existing + new_topics))[:20]  # preserve order, unique, cap
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
        """
        Atomically increment session_count and return the new value.
        Used to decide whether to trigger the adaptive quiz (every 5 sessions).
        """
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


def get_profile_store(
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> ProfileStore:
    return ProfileStore(db=db)


__all__ = ["ProfileStore", "get_profile_store"]
