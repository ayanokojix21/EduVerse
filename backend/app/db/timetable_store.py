from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.config import get_settings

class TimetableStore:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.settings = get_settings()
        self.collection = db[self.settings.mongo_timetables_collection]

    async def get_timetable(self, user_id: str) -> dict[str, Any] | None:
        """Fetch the current full state of the timetable JSON."""
        return await self.collection.find_one({"user_id": user_id})

    async def upsert_timetable(self, user_id: str, timetable_data: dict[str, Any]) -> None:
        """Overwrite the existing timetable with an updated version."""
        await self.collection.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "data": timetable_data,
                    "updated_at": datetime.now(timezone.utc)
                },
                "$setOnInsert": {"created_at": datetime.now(timezone.utc)}
            },
            upsert=True
        )
