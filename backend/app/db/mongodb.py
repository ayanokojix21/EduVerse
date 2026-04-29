"""
app/db/mongodb.py
────────────────
MongoDB Infrastructure — Local-First.

Connects to local MongoDB, creates indexes, and initializes
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import MongoClient

from app.config import get_settings

logger = logging.getLogger(__name__)

MONGO_CLIENT_STATE_KEY = "mongo_client"
MONGO_CLIENT_SYNC_STATE_KEY = "mongo_client_sync"
MONGO_DB_STATE_KEY = "mongo_db"


@asynccontextmanager
async def mongo_lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()

    logger.info("Connecting to MongoDB…")
    client = AsyncIOMotorClient(settings.mongo_uri, serverSelectionTimeoutMS=10000)
    sync_client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=10000)
    db = client[settings.mongo_db_name]

    try:
        await db.command("ping")
        sync_client.admin.command("ping")
        logger.info("MongoDB connected — db=%s", settings.mongo_db_name)

        await db[settings.mongo_oauth_tokens_collection].create_index(
            "user_id", unique=True
        )
        await db[settings.mongo_parent_chunks_collection].create_index(
            [("user_id", 1), ("course_id", 1), ("parent_id", 1)],
            unique=True,
        )
        await db[settings.mongo_parent_chunks_collection].create_index(
            [("metadata.source_doc_id", 1), ("metadata.chunk_index", 1)]
        )
        await db[settings.mongo_child_chunks_collection].create_index(
            [("user_id", 1), ("course_id", 1)]
        )
        await db[settings.mongo_child_chunks_collection].create_index("parent_id")

        await db[settings.mongo_semantic_cache_collection].create_index(
            [("user_id", 1), ("course_id", 1)]
        )
        await db[settings.mongo_user_profiles_collection].create_index(
            "user_id", unique=True
        )

        await db[settings.mongo_ingestion_jobs_collection].create_index(
            [("user_id", 1), ("course_id", 1)],
            unique=True,
        )
        await db[settings.mongo_cached_courses_collection].create_index(
            "user_id", unique=True
        )
        await db[settings.mongo_local_courses_collection].create_index(
            [("user_id", 1), ("id", 1)], unique=True
        )
        try:
            from langchain_core.globals import set_llm_cache
            from langchain_mongodb.cache import MongoDBAtlasSemanticCache
            from app.retrieval.retriever import build_embeddings

            cache_collection = sync_client[settings.mongo_db_name][settings.mongo_semantic_cache_collection]

            set_llm_cache(MongoDBAtlasSemanticCache(
                embedding=build_embeddings(settings),
                collection=cache_collection,
                index_name=settings.mongo_semantic_cache_vector_index_name,
            ))
            logger.info("Semantic Cache initialized on index: %s", settings.mongo_semantic_cache_vector_index_name)
        except Exception as exc:
            logger.warning("Semantic Caching unavailable (non-critical): %s", exc)

        # ── State Assignment ─────────────────────────────────────────────────
        setattr(app.state, MONGO_CLIENT_STATE_KEY, client)
        setattr(app.state, MONGO_CLIENT_SYNC_STATE_KEY, sync_client)
        setattr(app.state, MONGO_DB_STATE_KEY, db)

        logger.info("MongoDB Engine Ready.")
        yield
    finally:
        client.close()
        sync_client.close()
        logger.info("MongoDB clients closed.")


_motor_client_singleton: AsyncIOMotorClient | None = None

def get_motor_client() -> AsyncIOMotorClient:
    """Returns a singleton Motor client for scripts and background tasks."""
    global _motor_client_singleton
    if _motor_client_singleton is None:
        settings = get_settings()
        _motor_client_singleton = AsyncIOMotorClient(settings.mongo_uri, serverSelectionTimeoutMS=10000)
    return _motor_client_singleton


def get_db(request: Request) -> AsyncIOMotorDatabase:
    db = getattr(request.app.state, MONGO_DB_STATE_KEY, None)
    if db is None:
        raise RuntimeError("MongoDB is not initialized. Start app with DB lifespan enabled.")
    return db


def get_sync_client(request: Request) -> MongoClient:
    client = getattr(request.app.state, MONGO_CLIENT_SYNC_STATE_KEY, None)
    if client is None:
        raise RuntimeError("Sync MongoDB client is not initialized.")
    return client
