from __future__ import annotations

from fastapi import Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import Settings, get_settings
from app.db.mongodb import get_db
from app.db.oauth_tokens import NeedsReauthError, OAuthTokenService, get_oauth_token_service
from app.db.semantic_cache import SemanticCacheService, get_semantic_cache_service
from app.ingestion.chunker import chunk_documents
from app.ingestion.classroom_loader import ClassroomLoadError, load_course_documents
from app.ingestion.embedder import embed_and_store


class CourseIngestionService:
    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        token_service: OAuthTokenService,
        semantic_cache_service: SemanticCacheService,
        settings: Settings | None = None,
    ) -> None:
        self.db = db
        self.token_service = token_service
        self.semantic_cache_service = semantic_cache_service
        self.settings = settings or get_settings()

    async def ingest_course(
        self,
        user_id: str,
        course_id: str,
        force_refresh: bool = False,
    ) -> dict[str, int | bool | str]:
        if force_refresh:
            deleted_child, deleted_parent = await self._clear_course_chunks(user_id, course_id)
        else:
            deleted_child, deleted_parent = 0, 0

        credentials = await self.token_service.get_user_credentials(user_id)
        documents = await load_course_documents(
            user_id=user_id,
            course_id=course_id,
            credentials=credentials,
            settings=self.settings,
        )

        parent_chunks, child_chunks = chunk_documents(
            documents=documents,
            user_id=user_id,
            parent_chunk_size=self.settings.parent_chunk_size,
            child_chunk_size=self.settings.child_chunk_size,
            chunk_overlap=self.settings.chunk_overlap,
        )

        indexing_stats = await embed_and_store(
            user_id=user_id,
            course_id=course_id,
            parent_chunks=parent_chunks,
            child_chunks=child_chunks,
            db=self.db,
            settings=self.settings,
        )

        semantic_cache_deleted = await self.semantic_cache_service.clear_course_cache(
            user_id=user_id,
            course_id=course_id,
        )

        return {
            "user_id": user_id,
            "course_id": course_id,
            "force_refresh": force_refresh,
            "documents_loaded": len(documents),
            "parent_chunks": len(parent_chunks),
            "child_chunks": len(child_chunks),
            "cleared_child_chunks": deleted_child,
            "cleared_parent_chunks": deleted_parent,
            "semantic_cache_deleted": semantic_cache_deleted,
            **indexing_stats,
        }

    async def _clear_course_chunks(self, user_id: str, course_id: str) -> tuple[int, int]:
        # We DO NOT delete child chunks from MongoDB manually here.
        # LangChain's index() API (with SQLRecordManager) manages child chunks.
        # If we delete them from Mongo behind its back, the SQLite cache gets
        # out of sync, thinking they are still in Mongo, resulting in 0 inserts.
        parent_result = await self.db[self.settings.mongo_parent_chunks_collection].delete_many(
            {"user_id": user_id, "course_id": course_id}
        )
        return 0, int(parent_result.deleted_count)


def get_course_ingestion_service(
    db: AsyncIOMotorDatabase = Depends(get_db),
    token_service: OAuthTokenService = Depends(get_oauth_token_service),
    semantic_cache_service: SemanticCacheService = Depends(get_semantic_cache_service),
) -> CourseIngestionService:
    return CourseIngestionService(
        db=db,
        token_service=token_service,
        semantic_cache_service=semantic_cache_service,
    )


__all__ = [
    "ClassroomLoadError",
    "CourseIngestionService",
    "NeedsReauthError",
    "get_course_ingestion_service",
]
