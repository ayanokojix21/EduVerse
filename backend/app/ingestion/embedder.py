from __future__ import annotations

import warnings
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Tuple, Generator

warnings.filterwarnings(
    "ignore",
    message="Using SHA-1 for document hashing",
    category=UserWarning,
)

import anyio
from langchain_community.indexes._sql_record_manager import SQLRecordManager
from langchain_core.indexing import index
from langchain_core.documents import Document
from pymongo import MongoClient, ReplaceOne
from app.db.vector_repository import get_vector_repository
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.config import Settings, get_settings


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _extract_indexing_stat(result: Any, key: str) -> int:
    if isinstance(result, dict):
        return int(result.get(key, 0))
    return int(getattr(result, key, 0))


async def embed_and_store(
    user_id: str,
    course_id: str,
    parent_chunks: list[Document],
    child_chunks: list[Document],
    db: AsyncIOMotorDatabase,
    settings: Settings | None = None,
    cleanup: str = "full",
) -> dict[str, int]:
    resolved_settings = settings or get_settings()

    parent_collection = db[resolved_settings.mongo_parent_chunks_collection]
    child_collection = db[resolved_settings.mongo_child_chunks_collection]

    now = _utc_now_naive()
    parent_records: list[dict[str, Any]] = []
    for parent in parent_chunks:
        metadata = dict(parent.metadata or {})
        parent_records.append(
            {
                "parent_id": metadata["parent_id"],
                "content": parent.page_content,
                "metadata": metadata,
                "user_id": user_id,
                "course_id": course_id,
                "updated_at": now,
            }
        )

    parent_upserts = 0
    stale_parents_deleted = 0
    if parent_records:
        operations = [
            ReplaceOne(
                {
                    "user_id": user_id,
                    "course_id": course_id,
                    "parent_id": record["parent_id"],
                },
                record,
                upsert=True,
            )
            for record in parent_records
        ]
        write_result = await parent_collection.bulk_write(operations, ordered=False)
        parent_upserts = int((write_result.upserted_count or 0) + (write_result.modified_count or 0))

        if cleanup == "full":
            keep_parent_ids = [record["parent_id"] for record in parent_records]
            stale_parent_delete_result = await parent_collection.delete_many(
                {
                    "user_id": user_id,
                    "course_id": course_id,
                    "parent_id": {"$nin": keep_parent_ids},
                }
            )
            stale_parents_deleted = int(stale_parent_delete_result.deleted_count)
    elif cleanup == "full":
        clear_result = await parent_collection.delete_many(
            {"user_id": user_id, "course_id": course_id}
        )
        stale_parents_deleted = int(clear_result.deleted_count)

    if not child_chunks:
        if cleanup == "full":
            child_delete_result = await child_collection.delete_many(
                {"user_id": user_id, "course_id": course_id}
            )
            num_deleted = int(child_delete_result.deleted_count)
        else:
            num_deleted = 0

        return {
            "num_added": 0,
            "num_updated": 0,
            "num_deleted": num_deleted,
            "num_skipped": 0,
            "parent_upserts": parent_upserts,
            "stale_parents_deleted": stale_parents_deleted,
        }

    def _run_indexing_sync() -> Any:
        repo = get_vector_repository()
        with repo.get_vector_store_context(user_id, course_id) as (record_manager, vector_store, _):
            record_manager.create_schema()
            return index(
                child_chunks,
                record_manager,
                vector_store,
                cleanup=cleanup,
                source_id_key="source_id",
            )

    indexing_result = await anyio.to_thread.run_sync(_run_indexing_sync)

    return {
        "num_added": _extract_indexing_stat(indexing_result, "num_added"),
        "num_updated": _extract_indexing_stat(indexing_result, "num_updated"),
        "num_deleted": _extract_indexing_stat(indexing_result, "num_deleted"),
        "num_skipped": _extract_indexing_stat(indexing_result, "num_skipped"),
        "parent_upserts": parent_upserts,
        "stale_parents_deleted": stale_parents_deleted,
    }


async def wipe_course_vectors(user_id: str, course_id: str, settings: Settings | None = None) -> int:
    """Manually clear all child vectors and indexing traces for a course."""
    resolved = settings or get_settings()

    def _run_wipe_sync() -> int:
        repo = get_vector_repository()
        with repo.get_vector_store_context(user_id, course_id) as (record_manager, vector_store, _):
            all_keys = record_manager.list_keys()
            if not all_keys:
                return 0
            vector_store.delete(all_keys)
            record_manager.delete_keys(all_keys)
            return len(all_keys)

    return await anyio.to_thread.run_sync(_run_wipe_sync)


async def delete_file_vectors(user_id: str, course_id: str, filename: str, settings: Settings | None = None) -> int:
    """Targeted deletion of vectors for a specific file."""
    resolved = settings or get_settings()

    def _run_targeted_delete_sync() -> int:
        sync_client_tmp = MongoClient(resolved.mongo_uri)
        try:
            sync_collection = sync_client_tmp[resolved.mongo_db_name][resolved.mongo_child_chunks_collection]
            cursor = sync_collection.find(
                {"user_id": user_id, "course_id": course_id, "metadata.title": filename},
                {"_id": 1},
            )
            keys_to_delete = [str(doc["_id"]) for doc in cursor]
        finally:
            sync_client_tmp.close()

        if not keys_to_delete:
            return 0

        repo = get_vector_repository()
        with repo.get_vector_store_context(user_id, course_id) as (record_manager, vector_store, _):
            vector_store.delete(keys_to_delete)
            record_manager.delete_keys(keys_to_delete)
            return len(keys_to_delete)

    return await anyio.to_thread.run_sync(_run_targeted_delete_sync)
