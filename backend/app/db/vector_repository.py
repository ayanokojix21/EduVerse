"""
app/db/vector_repository.py
────────────────────────────
Vector Store Repository — Cloud Native.

Uses:
  - Nomic API (cloud) for text embeddings
  - MongoDB Atlas Vector Search for similarity search
  - MongoDBRecordManager for deduplication tracking (replaces SQLite)
"""
from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Generator, Tuple

from langchain_mongodb import MongoDBAtlasVectorSearch
from langchain_mongodb.indexes import MongoDBRecordManager
from langchain_nomic import NomicEmbeddings
from pymongo import MongoClient

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


class EduVerseRecordManager(MongoDBRecordManager):
    """
    Subclass of MongoDBRecordManager that overrides get_time() to use
    Python's time.time() instead of MongoDB server time.

    MongoDBRecordManager.get_time() reads `ping['operationTime']` which
    only exists on replica sets / MongoDB Atlas. On a standalone local
    MongoDB instance this raises a KeyError. Python's time.time() is
    perfectly correct for deduplication tracking purposes.
    """

    def get_time(self) -> float:
        return time.time()

    async def aget_time(self) -> float:
        return time.time()


class VectorRepository:
    """Encapsulates Nomic embeddings and MongoDB Atlas Vector Search connectivity."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def get_embeddings(self) -> NomicEmbeddings:
        """Returns cloud Nomic embeddings."""
        return NomicEmbeddings(
            model=self.settings.nomic_embedding_model,
            nomic_api_key=self.settings.nomic_api_key,
            dimensionality=768,
        )

    @contextmanager
    def get_vector_store_context(
        self, user_id: str, course_id: str
    ) -> Generator[Tuple[MongoDBRecordManager, MongoDBAtlasVectorSearch, MongoClient], None, None]:
        """Context manager to safely manage sync PyMongo connections and Vector Store handles."""
        sync_client = MongoClient(
            self.settings.mongo_uri,
            serverSelectionTimeoutMS=10000,
        )
        try:
            sync_collection = sync_client[self.settings.mongo_db_name][self.settings.mongo_child_chunks_collection]

            vector_store = MongoDBAtlasVectorSearch(
                collection=sync_collection,
                embedding=self.get_embeddings(),
                index_name=self.settings.mongo_child_vector_index_name,
                text_key="content",
            )

            # Scope dedup per-tenant by giving each user+course its own RM collection.
            # Without this, user A's indexed docs block user B's ingestion.
            rm_ns = f"record_manager_cache_{user_id}_{course_id}".replace("@", "_at_").replace(".", "_")
            rm_collection = sync_client[self.settings.mongo_db_name][rm_ns]
            record_manager = EduVerseRecordManager(
                collection=rm_collection,
            )

            yield record_manager, vector_store, sync_client
        finally:
            sync_client.close()

    def get_vector_store(self, sync_client: MongoClient) -> MongoDBAtlasVectorSearch:
        """Returns a vector store handle for a given sync client."""
        sync_collection = sync_client[self.settings.mongo_db_name][self.settings.mongo_child_chunks_collection]
        return MongoDBAtlasVectorSearch(
            collection=sync_collection,
            embedding=self.get_embeddings(),
            index_name=self.settings.mongo_child_vector_index_name,
            text_key="content",
        )

def get_vector_repository() -> VectorRepository:
    return VectorRepository()
