from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator, Tuple

from langchain_mongodb import MongoDBAtlasVectorSearch
from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
from langchain_community.indexes._sql_record_manager import SQLRecordManager
from pymongo import MongoClient

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

class VectorRepository:
    """Encapsulates FastEmbed initialization and MongoDB Atlas Vector Search connectivity."""
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def get_embeddings(self) -> FastEmbedEmbeddings:
        """Returns local FastEmbed embeddings."""
        return FastEmbedEmbeddings(
            model_name=self.settings.local_embedding_model,
            threads=self.settings.local_num_threads,
        )

    @contextmanager
    def get_vector_store_context(
        self, user_id: str, course_id: str
    ) -> Generator[Tuple[SQLRecordManager, MongoDBAtlasVectorSearch, MongoClient], None, None]:
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
            
            namespace = f"mongodb/{self.settings.mongo_db_name}/{self.settings.mongo_child_chunks_collection}/{user_id}/{course_id}"
            record_manager = SQLRecordManager(namespace, db_url=self.settings.record_manager_db_url)
            
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
