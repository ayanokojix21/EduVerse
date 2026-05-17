import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s:\t  %(message)s")
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
load_dotenv()

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.security import HTTPBearer

from app.api import api_router
from app.config import get_settings
from app.db import mongo_lifespan
from app.middleware import JWTAuthMiddleware

logger = logging.getLogger(__name__)

@asynccontextmanager
async def global_lifespan(app: FastAPI):
    """
    Orchestrated boot sequence for the EduVerse Backend.
    1. Connect to MongoDB (Async & Sync pools).
    2. Initialize LangGraph checkpointer with active DB connection.
    3. Compile global Agent StateGraph.
    """
    settings = get_settings()
    
    async with mongo_lifespan(app):
        try:
            from app.db.mongodb import MONGO_DB_STATE_KEY
            db = getattr(app.state, MONGO_DB_STATE_KEY)
            from app.db.ingestion_repository import IngestionJobRepository
            job_repo = IngestionJobRepository(db=db)
            await job_repo.reset_stale_jobs()

            from app.agents.graph import compile_graph
            from langgraph.checkpoint.mongodb import MongoDBSaver
            
            from app.db.mongodb import MONGO_CLIENT_SYNC_STATE_KEY
            
            sync_client = getattr(app.state, MONGO_CLIENT_SYNC_STATE_KEY)
            checkpointer = MongoDBSaver(sync_client, db_name=settings.mongo_db_name)
            
            await compile_graph(checkpointer)
            logger.info("EduVerse MAS compiled with shared persistent checkpointer.")
            
            yield
        except Exception as exc:
            logger.exception("FATAL: EduVerse MAS failed to compile: %s", exc)
            raise

def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=global_lifespan,
    )

    app.add_middleware(JWTAuthMiddleware)
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # ── CORS Setup ─────────────────────────────────────────────────────────────
    # Allow production frontend + local development origins
    origins = [
        settings.frontend_origin,
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:3000",
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/", tags=["health"])
    def read_root():
        return {"status": "EduVerse API is active", "environment": settings.app_env}

    app.include_router(api_router, dependencies=[Depends(HTTPBearer(auto_error=False, description="Enter your JWT generated from scripts/dev_jwt_generator.py"))])
    return app


app = create_app()
