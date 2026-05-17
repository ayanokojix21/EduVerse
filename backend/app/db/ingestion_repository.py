from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.config import Settings, get_settings
from app.db.mongodb import get_db
from app.schemas.db import IngestionJob

logger = logging.getLogger(__name__)

# Must be longer than the longest single phase (document loading with
# vision analysis can take 8-10 minutes for image-heavy PDFs).
STALE_JOB_TIMEOUT_SECONDS = 900  # 15 minutes


class IngestionJobRepository:
    def __init__(self, db: AsyncIOMotorDatabase, settings: Settings | None = None) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.collection_name = self.settings.mongo_ingestion_jobs_collection

    async def get_job(self, user_id: str, course_id: str) -> Optional[IngestionJob]:
        doc = await self.db[self.collection_name].find_one({"user_id": user_id, "course_id": course_id})
        if not doc:
            return None

        job = IngestionJob(**doc)

        if job.status in ("processing", "pending"):
            last_updated = job.last_updated
            # MongoDB may store naive datetimes — normalize to UTC
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=timezone.utc)
            age = datetime.now(timezone.utc) - last_updated
            if age > timedelta(seconds=STALE_JOB_TIMEOUT_SECONDS):
                logger.warning(
                    "Auto-recovering stale ingestion job for course %s "
                    "(stuck in '%s' for %s).",
                    course_id, job.status, age,
                )
                await self.update_status(
                    user_id, course_id, "failed",
                    error="Ingestion timed out (background task may have crashed). Please retry.",
                )
                job.status = "failed"
                job.error = "Ingestion timed out (background task may have crashed). Please retry."

        return job

    async def heartbeat(self, user_id: str, course_id: str) -> None:
        """Touch last_updated to signal the job is still alive.
        
        Called between long-running phases to prevent the staleness
        detector from killing an actively-running job.
        """
        await self.db[self.collection_name].update_one(
            {"user_id": user_id, "course_id": course_id, "status": "processing"},
            {"$set": {"last_updated": datetime.now(timezone.utc)}},
        )

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

    async def reset_stale_jobs(self) -> int:
        """
        Called once on server startup. Marks ALL processing/pending jobs as
        failed, because the worker threads that were running them no longer
        exist after a restart.
        """
        result = await self.db[self.collection_name].update_many(
            {"status": {"$in": ["processing", "pending"]}},
            {"$set": {
                "status": "failed",
                "error": "Server restarted during ingestion. Please retry.",
                "last_updated": datetime.now(timezone.utc),
            }},
        )
        if result.modified_count:
            logger.info(
                "Startup cleanup: reset %d stale ingestion job(s).",
                result.modified_count,
            )
        return result.modified_count


def get_ingestion_job_repository(
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> IngestionJobRepository:
    return IngestionJobRepository(db=db)
