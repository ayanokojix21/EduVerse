from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import anyio
from fastapi import Depends

from app.config import Settings, get_settings
from app.db.mongodb import get_db
from app.db.oauth_repository import OAuthTokenRepository, get_oauth_repository
from app.services.auth.classroom_service import ClassroomService
from app.schemas.api import UnifiedCourse

if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


class CourseService:
    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        settings: Settings,
        token_service: OAuthTokenRepository,
    ) -> None:
        self.db = db
        self.settings = settings
        self.token_service = token_service

    async def get_all_courses(self, user_id: str) -> list[UnifiedCourse]:
        is_guest = user_id.startswith("guest_")

        local_coll = self.db[self.settings.mongo_local_courses_collection]
        local_raw = await local_coll.find({"user_id": user_id}).to_list(length=None)

        google_raw = []
        if not is_guest:
            cache_coll = self.db[self.settings.mongo_cached_courses_collection]
            cached = await cache_coll.find_one({"user_id": user_id})

            cache_is_fresh = False
            if cached and cached.get("courses"):
                updated_at = cached.get("updated_at")
                if updated_at is not None:
                    # MongoDB may store naive datetimes — normalize to UTC
                    if updated_at.tzinfo is None:
                        updated_at = updated_at.replace(tzinfo=timezone.utc)
                    age = datetime.now(timezone.utc) - updated_at
                    cache_is_fresh = age.total_seconds() < 300  # 5 minutes

            if cache_is_fresh:
                google_raw = cached["courses"]
            else:
                # Cache is stale or empty — refresh from Google in background
                try:
                    credentials = await self.token_service.get_user_credentials(user_id)
                    google_raw = await anyio.to_thread.run_sync(ClassroomService.list_courses, credentials)

                    # Enrich with assignment counts (batched, not N+1)
                    async def enrich(c):
                        c["source"] = "google_classroom"
                        def get_count():
                            try:
                                from googleapiclient.discovery import build
                                local_service = build("classroom", "v1", credentials=credentials, cache_discovery=False)
                                res = local_service.courses().courseWork().list(courseId=c["id"]).execute()
                                return len(res.get("courseWork", []))
                            except Exception:
                                return 0
                        c["assignment_count"] = await anyio.to_thread.run_sync(get_count)

                    await asyncio.gather(*(enrich(c) for c in google_raw))
                    await cache_coll.update_one(
                        {"user_id": user_id},
                        {"$set": {"user_id": user_id, "courses": google_raw, "updated_at": datetime.now(timezone.utc)}},
                        upsert=True,
                    )
                except Exception as exc:
                    logger.warning("Course fetch fallback to cache for %s: %s", user_id, exc)
                    # Fall back to whatever we have in cache, even if stale
                    if cached and cached.get("courses"):
                        google_raw = cached["courses"]

        all_ids = [c.get("course_id") or c.get("id") for c in local_raw + google_raw]
        ingested = await self.db[self.settings.mongo_parent_chunks_collection].distinct(
            "course_id", {"user_id": user_id, "course_id": {"$in": all_ids}}
        )
        ingested_set = set(ingested)

        results: list[UnifiedCourse] = []
        for lc in local_raw:
            cid = lc["course_id"]
            results.append(UnifiedCourse(
                id=cid,
                name=lc["name"],
                source="local",
                description=lc.get("description"),
                is_ingested=cid in ingested_set,
                created_at=lc.get("created_at"),
            ))
        for gc in google_raw:
            gid = gc["id"]
            results.append(UnifiedCourse(
                id=gid,
                name=gc["name"],
                source="google_classroom",
                description=gc.get("description"),
                is_ingested=gid in ingested_set,
                assignment_count=gc.get("assignment_count", 0),
            ))
        return results

    async def create_local_course(self, user_id: str, name: str, description: str | None) -> dict:
        course_id = f"local_{uuid.uuid4().hex[:12]}"
        doc = {
            "course_id": course_id,
            "user_id": user_id,
            "name": name,
            "description": description,
            "source": "local",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        await self.db[self.settings.mongo_local_courses_collection].insert_one(doc)
        return {"id": course_id, "name": name}

    async def delete_course_full(self, user_id: str, course_id: str) -> None:
        await self.db[self.settings.mongo_parent_chunks_collection].delete_many({"user_id": user_id, "course_id": course_id})
        await self.db[self.settings.mongo_child_chunks_collection].delete_many({"user_id": user_id, "course_id": course_id})
        await self.db[self.settings.mongo_ingestion_jobs_collection].delete_many({"user_id": user_id, "course_id": course_id})

        if course_id.startswith("local_"):
            # ── Cloud Storage Wipe (Cloudinary) ───────────────────────────────
            if self.settings.has_cloudinary:
                try:
                    from app.services.core.storage_service import StorageService
                    storage = StorageService(self.settings)
                    await storage.delete_course_data(user_id, course_id)
                except Exception as exc:
                    logger.warning("Cloudinary course wipe non-critical failure: %s", exc)
            await self.db[self.settings.mongo_local_courses_collection].delete_one({"user_id": user_id, "course_id": course_id})

        from app.ingestion.embedder import wipe_course_vectors
        await wipe_course_vectors(user_id, course_id, settings=self.settings)

    async def delete_file(self, user_id: str, course_id: str, file_id: str) -> None:
        await self.db[self.settings.mongo_parent_chunks_collection].delete_many({
            "user_id": user_id, "course_id": course_id, "metadata.file_id": file_id
        })
        await self.db[self.settings.mongo_child_chunks_collection].delete_many({
            "user_id": user_id, "course_id": course_id, "metadata.file_id": file_id
        })
        from app.ingestion.embedder import delete_file_vectors
        await delete_file_vectors(user_id, course_id, file_id, self.settings)


def get_course_service(
    db=Depends(get_db),
    settings=Depends(get_settings),
    token_service=Depends(get_oauth_repository),
) -> CourseService:
    return CourseService(db, settings, token_service)
