from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File,Form, BackgroundTasks

from app.db.ingestion_repository import IngestionJobRepository, get_ingestion_job_repository
from app.services.core.storage_service import get_storage_service, StorageService
from app.ingestion.pipeline import (
    CourseIngestionService,
    get_course_ingestion_service,
)
from app.schemas.api import IngestRequest, IngestedFile

from app.db.mongodb import get_db, get_sync_client
from app.config import get_settings, Settings
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)
router = APIRouter()

# ── File Upload Security ────────────────────────────────────────────────────────
MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024  
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".docx"}
MAX_FILES_PER_COURSE = 500

@router.post("/")
async def ingest_course(
    payload: IngestRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    ingestion_service: CourseIngestionService = Depends(get_course_ingestion_service),
    job_repo: IngestionJobRepository = Depends(get_ingestion_job_repository),
) -> dict[str, str]:
    """Triggers the ingestion pipeline for a specific course/folder."""
    user_id = request.state.user_id

    # ── Guard: reject if ingestion is already running ────────────────────
    existing = await job_repo.get_job(user_id, payload.course_id)
    if existing and existing.status in ("processing", "pending"):
        return {
            "status": "already_running",
            "message": "Ingestion is already in progress for this course",
            "course_id": payload.course_id,
        }

    await job_repo.update_status(user_id, payload.course_id, "pending")
    
    background_tasks.add_task(
        ingestion_service.ingest_course,
        user_id=user_id,
        course_id=payload.course_id,
        force_refresh=payload.force_refresh,
        selected_item_ids=payload.selected_item_ids,
    )
    
    return {
        "status": "accepted",
        "message": "Ingestion started in the background",
        "course_id": payload.course_id
    }


@router.get("/status/{course_id}")
async def get_ingest_status(
    course_id: str,
    request: Request,
    job_repo: IngestionJobRepository = Depends(get_ingestion_job_repository),
    ingestion_service: CourseIngestionService = Depends(get_course_ingestion_service),
):
    """Checks the progress of a background ingestion job."""
    user_id = request.state.user_id
    job = await job_repo.get_job(user_id, course_id)
    
    # Get live count of successfully indexed files
    try:
        files = await ingestion_service.list_ingested_files(user_id, course_id)
        file_count = len(files)
    except Exception:
        file_count = 0

    if not job:
        return {
            "status": "none", 
            "message": "No ingestion job found",
            "current_file_count": file_count
        }
    
    # Merge job status with live stats
    response = job.model_dump() if hasattr(job, "model_dump") else dict(job)
    response["current_file_count"] = file_count

    if file_count == 0 and response.get("status") == "completed":
        response["status"] = "none"

    startup_restart_error = "Server restarted during ingestion"
    if (
        file_count == 0
        and response.get("status") == "failed"
        and startup_restart_error in (response.get("error") or "")
    ):
        response["status"] = "none"
        response["error"] = None
        
    return response


@router.post("/sync")
async def sync_course(
    payload: IngestRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    ingestion_service: CourseIngestionService = Depends(get_course_ingestion_service),
    job_repo: IngestionJobRepository = Depends(get_ingestion_job_repository),
) -> dict:
    """Forces a full sync and re-index of a course."""
    user_id = request.state.user_id

    # ── Guard: reject if ingestion is already running ────────────────────
    existing = await job_repo.get_job(user_id, payload.course_id)
    if existing and existing.status in ("processing", "pending"):
        return {
            "status": "already_running",
            "message": "Sync is already in progress for this course",
            "course_id": payload.course_id,
        }

    await job_repo.update_status(user_id, payload.course_id, "pending")
    
    background_tasks.add_task(
        ingestion_service.ingest_course,
        user_id=user_id,
        course_id=payload.course_id,
        force_refresh=True,
    )
    
    return {
        "status": "accepted",
        "message": "Sync started in the background",
        "course_id": payload.course_id
    }


@router.delete("/{course_id}")
async def delete_index(
    course_id: str,
    request: Request,
    ingestion_service: CourseIngestionService = Depends(get_course_ingestion_service),
):
    """Wipes the RAG index and all associated vectors for a course."""
    user_id = request.state.user_id
    success = await ingestion_service.delete_course_index(user_id, course_id)
    return {"success": success, "course_id": course_id, "message": "Index completely wiped."}


@router.delete("/{course_id}/files/{filename}")
async def delete_file(
    course_id: str,
    filename: str,
    request: Request,
    ingestion_service: CourseIngestionService = Depends(get_course_ingestion_service),
):
    """Removes a specific file and its vectors from the index."""
    user_id = request.state.user_id
    return await ingestion_service.delete_file_from_index(user_id, course_id, filename)


@router.get("/{course_id}/files", response_model=list[IngestedFile])
async def list_ingested_files(
    course_id: str,
    request: Request,
    ingestion_service: CourseIngestionService = Depends(get_course_ingestion_service),
) -> list[IngestedFile]:
    """Lists all documents currently indexed for a course."""
    return await ingestion_service.list_ingested_files(request.state.user_id, course_id)


@router.get("/{course_id}/coursework-files")
async def list_classroom_files(
    course_id: str,
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Lists all available Google Classroom items for selective ingestion.
    
    Returns a flat list with item_id so the frontend can present a picker
    before triggering selective ingestion.
    """
    from app.db.oauth_repository import OAuthTokenRepository
    from app.services.auth.classroom_service import ClassroomService
    from anyio import to_thread

    user_id = request.state.user_id
    settings = get_settings()
    oauth_repo = OAuthTokenRepository(db, settings)

    try:
        credentials = await oauth_repo.get_user_credentials(user_id)
        if not credentials:
            raise HTTPException(status_code=401, detail="Google Classroom not authorized.")

        items = await to_thread.run_sync(ClassroomService.list_coursework, credentials, course_id)

        return [
            {
                "item_id": item["id"],
                "title": item.get("title", "Untitled"),
                "type": item.get("type", "assignment"),
                "alternateLink": item.get("alternateLink", ""),
                "creationTime": item.get("creationTime", ""),
                "attachment_count": len(item.get("materials", [])),
            }
            for item in items
        ]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/upload")
async def upload_local_file(
    request: Request,
    course_id: str = Form(...),
    file: UploadFile = File(...),
    ingestion_service: CourseIngestionService = Depends(get_course_ingestion_service),
):
    """Handles manual PDF upload and immediate ingestion with security validation."""
    user_id = request.state.user_id
    
    # ── Validation 1: File extension ────────────────────────────────────────
    filename = file.filename or "unknown"
    file_ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400, 
            detail=f"File type '{file_ext}' not supported. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # ── Validation 2: File size ────────────────────────────────────────────
    file_bytes = await file.read()
    file_size = len(file_bytes)
    
    if file_size == 0:
        raise HTTPException(status_code=400, detail="File is empty")
    
    if file_size > MAX_FILE_SIZE_BYTES:
        max_mb = MAX_FILE_SIZE_BYTES / (1024 * 1024)
        raise HTTPException(
            status_code=413, 
            detail=f"File too large. Maximum size: {max_mb:.0f} MB. Got: {file_size / (1024*1024):.1f} MB"
        )
    
    # ── Validation 3: File count per course ─────────────────────────────────
    try:
        ingested_files = await ingestion_service.list_ingested_files(user_id, course_id)
        if len(ingested_files) >= MAX_FILES_PER_COURSE:
            raise HTTPException(
                status_code=429,
                detail=f"Course has reached maximum file limit ({MAX_FILES_PER_COURSE} files). Delete old files to upload new ones."
            )
    except Exception as exc:
        logger.warning(f"Could not check file count: {exc}")
    
    # ── Ingest ──────────────────────────────────────────────────────────────
    try:
        return await ingestion_service.ingest_local_document(
            user_id=user_id, course_id=course_id, filename=filename, file_bytes=file_bytes
        )
    except Exception as exc:
        logger.error("Failed to ingest local file: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to parse binary document")


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
    
    sync_client = get_sync_client(request)
    
    query = payload.get("query", "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="Search query cannot be empty.")
        
    chain = get_retrieval_chain(request.state.user_id, course_id, db, sync_client, settings)
    result = await chain.ainvoke(query)

    docs = result.get("documents", [])
    return {
        "documents": [
            {
                "content": getattr(d, "page_content", d.get("content", "")),
                "metadata": getattr(d, "metadata", d.get("metadata", {})),
            }
            for d in docs
        ]
    }
