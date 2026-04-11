from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import get_settings

logger = logging.getLogger(__name__)

MONGO_CLIENT_STATE_KEY = "mongo_client"
MONGO_DB_STATE_KEY = "mongo_db"


@asynccontextmanager
async def mongo_lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()

    logger.info("Connecting to MongoDB…")
    client = AsyncIOMotorClient(settings.mongo_uri, serverSelectionTimeoutMS=10000)
    db = client[settings.mongo_db_name]

    await db.command("ping")
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

    # tavily usage: unique per date
    await db[settings.mongo_tavily_usage_collection].create_index(
        "date", unique=True
    )

    # ── Warm up the CrossEncoder reranker (avoids first-request cold start) ──
    try:
        from app.retrieval.reranker import warm_up_reranker
        await warm_up_reranker()
        logger.info("CrossEncoder reranker warmed up.")
    except Exception as exc:          # noqa: BLE001
        logger.warning("Reranker warm-up failed (non-fatal): %s", exc)

    # ── Compile LangGraph agent pipeline ────────────────────────────────────
    try:
        from app.agents.graph import compile_graph
        from langgraph.checkpoint.mongodb.aio import AsyncMongoDBSaver # type: ignore[import-untyped]
        
        async with AsyncMongoDBSaver.from_conn_string(settings.mongo_uri, db_name=settings.mongo_db_name) as checkpointer:
            await compile_graph(checkpointer)
            logger.info("LangGraph agent pipeline compiled and ready.")
            
            setattr(app.state, MONGO_CLIENT_STATE_KEY, client)
            setattr(app.state, MONGO_DB_STATE_KEY, db)
            
            # App lifecycle block - checkpointer remains active
            yield
            
    except Exception as exc:          # noqa: BLE001
        logger.error("Lifespan error: %s", exc)
        raise
    finally:
        client.close()
        logger.info("MongoDB client closed.")


def get_motor_client() -> AsyncIOMotorClient:
    """Create a standalone Motor client for scripts and local tooling."""
    settings = get_settings()
    return AsyncIOMotorClient(settings.mongo_uri, serverSelectionTimeoutMS=10000)


def get_db(request: Request) -> AsyncIOMotorDatabase:
    db = getattr(request.app.state, MONGO_DB_STATE_KEY, None)
    if db is None:
        raise RuntimeError("MongoDB is not initialized. Start app with DB lifespan enabled.")
    return db
