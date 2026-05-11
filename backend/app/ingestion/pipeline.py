"""
app/ingestion/pipeline.py
──────────────────────────
Course Ingestion Pipeline

Supports:
1. Google Classroom sync (when online + authenticated)
2. Local PDF upload (always works)
3. Incremental and full re-indexing
"""
from __future__ import annotations

import logging
from typing import Any

import anyio
from fastapi import Depends
from langchain_core.documents import Document
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import Settings, get_settings
from app.db.ingestion_repository import IngestionJobRepository, get_ingestion_job_repository
from app.db.mongodb import get_db
from app.db.oauth_repository import OAuthTokenRepository, get_oauth_repository
from app.db.semantic_cache_repository import SemanticCacheRepository, get_semantic_cache_repository
from app.ingestion.chunker import chunk_documents
from app.ingestion.classroom_loader import ClassroomLoadError, load_course_documents
from app.ingestion.embedder import embed_and_store, wipe_course_vectors, delete_file_vectors
from app.services.core.storage_service import StorageService, get_storage_service

logger = logging.getLogger(__name__)


class CourseIngestionService:
    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        token_service: OAuthTokenRepository,
        semantic_cache_service: SemanticCacheRepository,
        job_service: IngestionJobRepository,
        storage_service: StorageService,
        settings: Settings | None = None,
    ) -> None:
        self.db = db
        self.token_service = token_service
        self.semantic_cache_service = semantic_cache_service
        self.job_service = job_service
        self.storage_service = storage_service
        self.settings = settings or get_settings()

    async def ingest_course(
        self,
        user_id: str,
        course_id: str,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """Background worker: syncs documents from Google Classroom and indexes them."""
        await self.job_service.update_status(user_id, course_id, "processing")

        if user_id.startswith("guest_"):
            error_msg = "Guest users cannot sync with Google Classroom. Please upload local files."
            await self.job_service.update_status(user_id, course_id, "failed", error=error_msg)
            return {"error": error_msg}

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
            logger.error("Ingestion failed for course %s: %s", course_id, error_msg)
            await self.job_service.update_status(user_id, course_id, "failed", error=error_msg)
            raise

    async def delete_course_index(self, user_id: str, course_id: str) -> bool:
        await self._clear_course_chunks(user_id, course_id)
        await wipe_course_vectors(user_id, course_id, settings=self.settings)
        await self.semantic_cache_service.clear_course_cache(user_id=user_id, course_id=course_id)
        await self.db[self.settings.mongo_ingestion_jobs_collection].delete_one(
            {"user_id": user_id, "course_id": course_id}
        )
        return True

    async def delete_file_from_index(self, user_id: str, course_id: str, filename: str) -> dict:
        """Targeted deletion of a specific file from the course index."""
        parent_coll = self.db[self.settings.mongo_parent_chunks_collection]
        parents = await parent_coll.find(
            {"user_id": user_id, "course_id": course_id, "metadata.title": filename}
        ).to_list(length=None)
        parent_ids = [p["parent_id"] for p in parents]

        await parent_coll.delete_many(
            {"user_id": user_id, "course_id": course_id, "metadata.title": filename}
        )

        deleted_vectors = await delete_file_vectors(user_id, course_id, filename, settings=self.settings)

        child_coll = self.db[self.settings.mongo_child_chunks_collection]
        await child_coll.delete_many(
            {"user_id": user_id, "course_id": course_id, "metadata.title": filename}
        )

        await self.semantic_cache_service.clear_course_cache(user_id=user_id, course_id=course_id)

        return {
            "success": True,
            "filename": filename,
            "parent_chunks_deleted": len(parent_ids),
            "child_vectors_deleted": deleted_vectors,
        }

    async def ingest_local_document(
        self, user_id: str, course_id: str, filename: str, file_bytes: bytes
    ) -> dict:
        """Ingests a single local document (PDF, Docx, Image, etc.)."""
        local_link = await self.storage_service.save_file(
            user_id, course_id, filename, file_bytes
        )
        parent_chunks, child_chunks = await anyio.to_thread.run_sync(
            self._parse_and_chunk_local,
            user_id,
            course_id,
            filename,
            file_bytes,
            local_link,
        )

        indexing_stats = await embed_and_store(
            user_id=user_id,
            course_id=course_id,
            parent_chunks=parent_chunks,
            child_chunks=child_chunks,
            db=self.db,
            settings=self.settings,
            cleanup="incremental",
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

    async def list_ingested_files(self, user_id: str, course_id: str) -> list[dict]:
        """Lists unique documents ingested for a course with metadata summary."""
        cursor = self.db[self.settings.mongo_parent_chunks_collection].aggregate([
            {"$match": {"user_id": user_id, "course_id": course_id}},
            {"$group": {
                "_id": {"$ifNull": ["$metadata.source", "$metadata.title"]}, 
                "total_chunks": {"$sum": 1},
                "title": {"$first": "$metadata.title"}
            }}
        ])
        files = await cursor.to_list(length=None)
        return [
            {
                "filename": f.get("title") or (f["_id"].split("/")[-1] if "/" in f["_id"] else f["_id"]), 
                "chunk_count": f["total_chunks"],
                "source": f["_id"]
            } for f in files
        ]

    def _parse_and_chunk_local(
        self,
        user_id: str,
        course_id: str,
        filename: str,
        file_bytes: bytes,
        local_link: str,
    ) -> tuple[list[Document], list[Document]]:
        """Synchronous helper for parsing and chunking local files of any supported format."""
        from app.utils.llm_pool import RoundRobinLLM
        from app.ingestion.classroom_loader import MarkdownPyMuPDFParser
        from langchain_core.documents.base import Blob
        import mimetypes
        from langchain_google_classroom.parsers import get_parser

        vision_llm = RoundRobinLLM.for_role("vision", temperature=0)
        
        mime_type, _ = mimetypes.guess_type(filename)
        mime_type = mime_type or "application/octet-stream"
        
        if mime_type == "application/pdf":
            parser = MarkdownPyMuPDFParser(vision_model=vision_llm)
        else:
            parser = get_parser(mime_type)
            if not parser:
                # Fallback to simple text parser
                class FallbackTextParser:
                    def lazy_parse(self, blob: Blob):
                        from langchain_core.documents import Document
                        text = blob.as_bytes().decode("utf-8", errors="replace")
                        yield Document(page_content=text, metadata={"page_number": 1})
                parser = FallbackTextParser()
            elif hasattr(parser, "vision_model"):
                setattr(parser, "vision_model", vision_llm)

        blob = Blob(data=file_bytes, source=filename, mimetype=mime_type)
        docs = list(parser.lazy_parse(blob))

        for doc in docs:
            doc.metadata.update({
                "source": "local_upload",
                "title": filename,
                "user_id": user_id,
                "course_id": course_id,
                "alternate_link": local_link,
                "item_id": f"local_{filename}",
            })

        parent_chunks, child_chunks = chunk_documents(
            documents=docs,
            user_id=user_id,
            parent_chunk_size=self.settings.parent_chunk_size,
            child_chunk_size=self.settings.child_chunk_size,
            chunk_overlap=self.settings.chunk_overlap,
        )

        return parent_chunks, child_chunks

    async def _clear_course_chunks(self, user_id: str, course_id: str) -> tuple[int, int]:
        """Clears both parent and child chunks from MongoDB."""
        child_result = await self.db[self.settings.mongo_child_chunks_collection].delete_many(
            {"user_id": user_id, "course_id": course_id}
        )
        parent_result = await self.db[self.settings.mongo_parent_chunks_collection].delete_many(
            {"user_id": user_id, "course_id": course_id}
        )

        logger.info(
            "Cleanup for course %s: %d child, %d parent chunks removed.",
            course_id, child_result.deleted_count, parent_result.deleted_count,
        )

        return int(child_result.deleted_count), int(parent_result.deleted_count)


def get_course_ingestion_service(
    db: AsyncIOMotorDatabase = Depends(get_db),
    token_service: OAuthTokenRepository = Depends(get_oauth_repository),
    semantic_cache_service: SemanticCacheRepository = Depends(get_semantic_cache_repository),
    job_service: IngestionJobRepository = Depends(get_ingestion_job_repository),
    storage_service: StorageService = Depends(get_storage_service),
) -> CourseIngestionService:
    return CourseIngestionService(
        db=db,
        token_service=token_service,
        semantic_cache_service=semantic_cache_service,
        job_service=job_service,
        storage_service=storage_service,
    )


__all__ = [
    "ClassroomLoadError",
    "CourseIngestionService",
    "get_course_ingestion_service",
]
