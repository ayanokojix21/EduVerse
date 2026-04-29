from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import Settings, get_settings
from app.db.mongodb import get_db
from app.db.oauth_repository import get_oauth_repository
from app.services.core.course_service import get_course_service, CourseService
from app.schemas.api import LocalCourseCreate, UnifiedCourse

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/", response_model=list[UnifiedCourse])
async def get_courses(
    request: Request,
    service: CourseService = Depends(get_course_service),
):
    """Unified dashboard: Lists all classroom and local courses."""
    return await service.get_all_courses(request.state.user_id)


@router.post("/", response_model=dict)
async def create_local_course(
    payload: LocalCourseCreate,
    request: Request,
    service: CourseService = Depends(get_course_service),
):
    """Create a new local folder/workspace."""
    return await service.create_local_course(request.state.user_id, payload.name, payload.description)


@router.delete("/{course_id}")
async def delete_course(
    course_id: str,
    request: Request,
    service: CourseService = Depends(get_course_service),
):
    """Deletes a local folder and its associated RAG index."""
    await service.delete_course_full(request.state.user_id, course_id)
    return {"success": True, "course_id": course_id}


@router.delete("/{course_id}/files/{file_id}")
async def delete_individual_file(
    course_id: str,
    file_id: str,
    request: Request,
    service: CourseService = Depends(get_course_service),
):
    """Removes a specific file and its vectors from a course."""
    await service.delete_file(request.state.user_id, course_id, file_id)
    return {"success": True, "file_id": file_id}


@router.post("/{course_id}/ingest")
async def ingest_course(
    course_id: str,
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Triggers the ingestion pipeline for a specific course/folder."""
    user_id = request.state.user_id
    from app.ingestion.pipeline import get_course_ingestion_service
    ingestion_service = get_course_ingestion_service(db, settings)
    asyncio.create_task(ingestion_service.ingest_course(user_id, course_id))
    return {"message": "Ingestion started", "course_id": course_id}


@router.get("/{course_id}/coursework")
async def get_coursework(
    course_id: str,
    request: Request,
    token_repo=Depends(get_oauth_repository),
):
    from app.services import list_coursework
    try:
        credentials = await token_repo.get_user_credentials(request.state.user_id)
        from anyio import to_thread
        return await to_thread.run_sync(list_coursework, credentials, course_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{course_id}/context")
async def get_chat_context(
    course_id: str,
    request: Request,
    payload: dict,
    db: AsyncIOMotorDatabase = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Fetches RAG context for a query (Browser-Native Mode)."""
    from app.retrieval.retriever import get_retrieval_chain
    from pymongo import MongoClient
    from anyio import to_thread
    
    def run_retrieval():
        with MongoClient(settings.mongo_uri) as sync_client:
            chain = get_retrieval_chain(request.state.user_id, course_id, db, sync_client, settings)
            return chain.invoke(payload.get("query", ""))

    result = await to_thread.run_sync(run_retrieval)
    return {
        "documents": [{"content": d.page_content, "metadata": d.metadata} for d in result.get("documents", [])]
    }
