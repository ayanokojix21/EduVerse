from __future__ import annotations

import warnings
from datetime import datetime, timezone
from typing import Any

# The LangChain indexing API uses SHA-1 for document fingerprinting. We accept
# this risk — our use case (chunk deduplication) does not require collision
# resistance. Suppress the noise so server logs stay clean.
warnings.filterwarnings(
    "ignore",
    message="Using SHA-1 for document hashing",
    category=UserWarning,
)

import anyio
from langchain.indexes import SQLRecordManager, index
from langchain_core.documents import Document
from langchain_mongodb import MongoDBAtlasVectorSearch
from langchain_nomic import NomicEmbeddings
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import MongoClient, ReplaceOne

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
) -> dict[str, int]:
    resolved_settings = settings or get_settings()

    if not resolved_settings.nomic_api_key:
        raise ValueError("NOMIC_API_KEY is required for ingestion embeddings")

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

        keep_parent_ids = [record["parent_id"] for record in parent_records]
        stale_parent_delete_result = await parent_collection.delete_many(
            {
                "user_id": user_id,
                "course_id": course_id,
                "parent_id": {"$nin": keep_parent_ids},
            }
        )
        stale_parents_deleted = int(stale_parent_delete_result.deleted_count)
    else:
        clear_result = await parent_collection.delete_many(
            {"user_id": user_id, "course_id": course_id}
        )
        stale_parents_deleted = int(clear_result.deleted_count)

    if not child_chunks:
        child_delete_result = await child_collection.delete_many(
            {"user_id": user_id, "course_id": course_id}
        )
        return {
            "num_added": 0,
            "num_updated": 0,
            "num_deleted": int(child_delete_result.deleted_count),
            "num_skipped": 0,
            "parent_upserts": parent_upserts,
            "stale_parents_deleted": stale_parents_deleted,
        }

    def _run_indexing_sync() -> Any:
        # langchain-mongodb expects a synchronous PyMongo collection.
        sync_client = MongoClient(
            resolved_settings.mongo_uri,
            serverSelectionTimeoutMS=10000,
        )
        try:
            sync_collection = sync_client[resolved_settings.mongo_db_name][
                resolved_settings.mongo_child_chunks_collection
            ]

            embeddings = NomicEmbeddings(
                model=resolved_settings.nomic_embedding_model,
                nomic_api_key=resolved_settings.nomic_api_key,
            )

            vector_store = MongoDBAtlasVectorSearch(
                collection=sync_collection,
                embedding=embeddings,
                index_name=resolved_settings.mongo_child_vector_index_name,
                text_key="content",
            )

            namespace = (
                f"mongodb/{resolved_settings.mongo_db_name}/"
                f"{resolved_settings.mongo_child_chunks_collection}/{user_id}/{course_id}"
            )
            record_manager = SQLRecordManager(
                namespace,
                db_url=resolved_settings.record_manager_db_url,
            )

            record_manager.create_schema()
            return index(
                child_chunks,
                record_manager,
                vector_store,
                cleanup="incremental",
                source_id_key="source_id",
            )
        finally:
            sync_client.close()

    indexing_result = await anyio.to_thread.run_sync(_run_indexing_sync)

    return {
        "num_added": _extract_indexing_stat(indexing_result, "num_added"),
        "num_updated": _extract_indexing_stat(indexing_result, "num_updated"),
        "num_deleted": _extract_indexing_stat(indexing_result, "num_deleted"),
        "num_skipped": _extract_indexing_stat(indexing_result, "num_skipped"),
        "parent_upserts": parent_upserts,
        "stale_parents_deleted": stale_parents_deleted,
    }
