from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.config import Settings, get_settings
from app.db.mongodb import get_db
from app.schemas.db import IngestionJob

class IngestionJobRepository:
    def __init__(self, db: AsyncIOMotorDatabase, settings: Settings | None = None) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.collection_name = self.settings.mongo_ingestion_jobs_collection

    async def get_job(self, user_id: str, course_id: str) -> Optional[IngestionJob]:
        doc = await self.db[self.collection_name].find_one({"user_id": user_id, "course_id": course_id})
        if doc:
            return IngestionJob(**doc)
        return None

    async def update_status(
        self, 
        user_id: str, 
        course_id: str, 
        status: str, 
        error: Optional[str] = None,
        job_metadata: Optional[dict] = None
    ) -> None:
        update_data = {
            "status": status,
            "error": error,
            "last_updated": datetime.now(timezone.utc),
        }
        if job_metadata:
            update_data["metadata"] = job_metadata

        await self.db[self.collection_name].update_one(
            {"user_id": user_id, "course_id": course_id},
            {"$set": update_data},
            upsert=True
        )


def get_ingestion_job_repository(
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> IngestionJobRepository:
    return IngestionJobRepository(db=db)
