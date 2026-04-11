from __future__ import annotations
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.config import get_settings

class EventStore:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.settings = get_settings()
        self.collection = db[self.settings.mongo_events_collection]

    async def add_events(self, user_id: str, events: list[dict]):
        """Save extracted events to long-term memory."""
        if not events: return
        for event in events:
            # Upsert prevents duplicates if the same email is processed twice
            await self.collection.update_one(
                {"user_id": user_id, "event": event.get("event"), "date": event.get("date")},
                {"$set": {**event, "updated_at": datetime.now(timezone.utc)}},
                upsert=True
            )

    async def get_events_for_date(self, user_id: str, target_date: str) -> list[dict]:
        """Retrieve all events stored for a specific date YYYY-MM-DD."""
        cursor = self.collection.find({"user_id": user_id, "date": target_date})
        return await cursor.to_list(length=100)
