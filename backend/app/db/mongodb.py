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

    await db.command("ping")
    sync_client.admin.command("ping")
    logger.info("MongoDB connected — db=%s", settings.mongo_db_name)

    # ── Regular (non-Atlas) indexes ──────────────────────────────────────────
    # oauth_tokens: unique per user
    await db[settings.mongo_oauth_tokens_collection].create_index(
        "user_id", unique=True
    )

    # parent chunks: unique per (user, course, parent_id)
    await db[settings.mongo_parent_chunks_collection].create_index(
        [("user_id", 1), ("course_id", 1), ("parent_id", 1)],
        unique=True,
    )

    # sliding window fetches: metadata.source_doc_id + metadata.chunk_index
    await db[settings.mongo_parent_chunks_collection].create_index(
        [("metadata.source_doc_id", 1), ("metadata.chunk_index", 1)]
    )

    # child chunks: lookup by (user, course)
    await db[settings.mongo_child_chunks_collection].create_index(
        [("user_id", 1), ("course_id", 1)]
    )
    # child chunks: fast parent_id lookup during parent fetch
    await db[settings.mongo_child_chunks_collection].create_index("parent_id")

    # semantic cache: scoped per (user, course)
    await db[settings.mongo_semantic_cache_collection].create_index(
        [("user_id", 1), ("course_id", 1)]
    )

    # user profiles: unique per user
    await db[settings.mongo_user_profiles_collection].create_index(
        "user_id", unique=True
    )

    # ingestion jobs: lookup by (user, course)
    await db[settings.mongo_ingestion_jobs_collection].create_index(
        [("user_id", 1), ("course_id", 1)],
        unique=True,
    )

    # ── Compile LangGraph agent pipeline ────────────────────────────────────
    try:
        from app.agents.graph import compile_graph
        from langgraph.checkpoint.mongodb.aio import AsyncMongoDBSaver # type: ignore[import-untyped]
        
        async with AsyncMongoDBSaver.from_conn_string(settings.mongo_uri, db_name=settings.mongo_db_name) as checkpointer:
            await compile_graph(checkpointer)
            logger.info("LangGraph agent pipeline compiled.")
            
            # Eagerly warm up the LLM pools in the background
            from app.utils.llm_pool import RoundRobinLLM
            import asyncio
            asyncio.create_task(RoundRobinLLM.warm_up())
            
            logger.info("EduVerse AI Engine ready.")
            
            setattr(app.state, MONGO_CLIENT_STATE_KEY, client)
            setattr(app.state, MONGO_CLIENT_SYNC_STATE_KEY, sync_client)
            setattr(app.state, MONGO_DB_STATE_KEY, db)
            
            # App lifecycle block - checkpointer remains active
            yield
            
    except Exception as exc:          # noqa: BLE001
        logger.error("Lifespan error: %s", exc)
        raise
    finally:
        client.close()
        sync_client.close()
        logger.info("MongoDB clients (async & sync) closed.")


def get_motor_client() -> AsyncIOMotorClient:
    """Create a standalone Motor client for scripts and local tooling."""
    settings = get_settings()
    return AsyncIOMotorClient(settings.mongo_uri, serverSelectionTimeoutMS=10000)


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
