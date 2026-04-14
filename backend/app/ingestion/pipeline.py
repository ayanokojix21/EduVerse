from __future__ import annotations

from fastapi import Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from typing import Any
from app.config import Settings, get_settings
from app import db
from app.db.ingestion_store import IngestionJobService, get_ingestion_job_service
from app.db.mongodb import get_db
from app.db.oauth_tokens import NeedsReauthError, OAuthTokenService, get_oauth_token_service
from app.db.semantic_cache import SemanticCacheService, get_semantic_cache_service
from app.ingestion.chunker import chunk_documents
from app.ingestion.classroom_loader import ClassroomLoadError, load_course_documents
from app.ingestion.embedder import embed_and_store, wipe_course_vectors, delete_file_vectors
import logging

logger = logging.getLogger(__name__)


class CourseIngestionService:
    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        token_service: OAuthTokenService,
        semantic_cache_service: SemanticCacheService,
        job_service: IngestionJobService,
        settings: Settings | None = None,
    ) -> None:
        self.db = db
        self.token_service = token_service
        self.semantic_cache_service = semantic_cache_service
        self.job_service = job_service
        self.settings = settings or get_settings()

    async def ingest_course(
        self,
        user_id: str,
        course_id: str,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """
        Worker function intended to run in the background.
        Manages job status in MongoDB and executes the ingestion pipeline.
        """
        await self.job_service.update_status(user_id, course_id, "processing")
        
        try:
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

            results = {
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
            
            await self.job_service.update_status(
                user_id, course_id, "completed", job_metadata=results
            )
            return results

        except Exception as exc:
            error_msg = str(exc)
            logger.error(f"Ingestion failed for course {course_id}: {error_msg}")
            await self.job_service.update_status(user_id, course_id, "failed", error=error_msg)
            raise

    async def delete_course_index(self, user_id: str, course_id: str) -> bool:
        await self._clear_course_chunks(user_id, course_id)
        await wipe_course_vectors(user_id, course_id, settings=self.settings)
        await self.semantic_cache_service.clear_course_cache(user_id=user_id, course_id=course_id)
        # Also clear the job status
        await self.db[self.settings.mongo_ingestion_jobs_collection].delete_one(
            {"user_id": user_id, "course_id": course_id}
        )
        return True

    async def delete_file_from_index(self, user_id: str, course_id: str, filename: str) -> dict:
        """
        Targeted deletion of a specific file from the course index.
        """
        # 1. Delete from MongoDB Parent Chunks (and get parent_ids)
        parent_coll = self.db[self.settings.mongo_parent_chunks_collection]
        parents = await parent_coll.find({"user_id": user_id, "course_id": course_id, "metadata.title": filename}).to_list(length=None)
        parent_ids = [p["parent_id"] for p in parents]
        
        await parent_coll.delete_many({"user_id": user_id, "course_id": course_id, "metadata.title": filename})
        
        # 2. Delete from Vector Store and Record Manager
        child_coll = self.db[self.settings.mongo_child_chunks_collection]
        children = await child_coll.find({"user_id": user_id, "course_id": course_id, "metadata.title": filename}).to_list(length=None)
        
        # In our system, child chunks in MongoDB might not store the 'source_id' used by langchain,
        deleted_vectors = await delete_file_vectors(user_id, course_id, filename, settings=self.settings)
        
        # 3. Finally delete child chunks from MongoDB
        await child_coll.delete_many({"user_id": user_id, "course_id": course_id, "metadata.title": filename})
        
        await self.semantic_cache_service.clear_course_cache(user_id=user_id, course_id=course_id)
        
        return {
            "success": True,
            "filename": filename,
            "parent_chunks_deleted": len(parent_ids),
            "child_vectors_deleted": deleted_vectors
        }

    async def ingest_local_document(self, user_id: str, course_id: str, filename: str, file_bytes: bytes) -> dict:
        from app.services.groq_vision import build_vision_model
        from app.ingestion.classroom_loader import MarkdownPyMuPDFParser
        from langchain_core.documents.base import Blob
        
        vision_model = build_vision_model(self.settings)
        parser = MarkdownPyMuPDFParser(vision_model=vision_model)
        
        # Create a blob for the parser
        blob = Blob(data=file_bytes, source=filename)
        
        # Parse using the multimodal parser
        docs = list(parser.lazy_parse(blob))
        
        for doc in docs:
            doc.metadata.update({
                "source": "local_upload",
                "title": filename,
                "user_id": user_id,
                "course_id": course_id,
                "alternate_link": "",
                "item_id": f"local_{filename}",
            })
        
        parent_chunks, child_chunks = chunk_documents(
            documents=docs,
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
        
        await self.semantic_cache_service.clear_course_cache(user_id=user_id, course_id=course_id)
        
        return {
            "user_id": user_id,
            "course_id": course_id,
            "filename": filename,
            "parent_chunks": len(parent_chunks),
            "child_chunks": len(child_chunks),
            **indexing_stats,
        }

    async def _clear_course_chunks(self, user_id: str, course_id: str) -> tuple[int, int]:
        """
        Clears both parent and child chunks from MongoDB to prevent orphaned data.
        """
        # 1. Clear Child Chunks (Actual vector storage in MongoDB)
        child_result = await self.db[self.settings.mongo_child_chunks_collection].delete_many(
            {"user_id": user_id, "course_id": course_id}
        )
        # 2. Clear Parent Chunks
        parent_result = await self.db[self.settings.mongo_parent_chunks_collection].delete_many(
            {"user_id": user_id, "course_id": course_id}
        )
        
        logger.info(
            "Cleanup for course %s complete: %d child chunks, %d parent chunks removed.",
            course_id, child_result.deleted_count, parent_result.deleted_count
        )
        
        return int(child_result.deleted_count), int(parent_result.deleted_count)


def get_course_ingestion_service(
    db: AsyncIOMotorDatabase = Depends(get_db),
    token_service: OAuthTokenService = Depends(get_oauth_token_service),
    semantic_cache_service: SemanticCacheService = Depends(get_semantic_cache_service),
    job_service: IngestionJobService = Depends(get_ingestion_job_service),
) -> CourseIngestionService:
    return CourseIngestionService(
        db=db,
        token_service=token_service,
        semantic_cache_service=semantic_cache_service,
        job_service=job_service,
    )


__all__ = [
    "ClassroomLoadError",
    "CourseIngestionService",
    "NeedsReauthError",
    "get_course_ingestion_service",
]
