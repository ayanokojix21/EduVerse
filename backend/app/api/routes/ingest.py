from fastapi import APIRouter, Depends, HTTPException, Request, status, UploadFile, File, BackgroundTasks
from pydantic import BaseModel, Field

from app.db.ingestion_store import IngestionJobService, get_ingestion_job_service
from app.ingestion.pipeline import (
    CourseIngestionService,
    get_course_ingestion_service,
)

router = APIRouter()

class IngestRequest(BaseModel):
    course_id: str = Field(min_length=1)
    force_refresh: bool = False


@router.post("/ingest")
async def ingest_course(
    payload: IngestRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    ingestion_service: CourseIngestionService = Depends(get_course_ingestion_service),
    job_service: IngestionJobService = Depends(get_ingestion_job_service),
) -> dict[str, str]:
    user_id = request.state.user_id
    
    # 1. Initialize job status
    await job_service.update_status(user_id, payload.course_id, "pending")
    
    # 2. Trigger background task
    background_tasks.add_task(
        ingestion_service.ingest_course,
        user_id=user_id,
        course_id=payload.course_id,
        force_refresh=payload.force_refresh,
    )
    
    return {
        "status": "accepted",
        "message": "Ingestion started in the background",
        "course_id": payload.course_id
    }


@router.get("/ingest/status/{course_id}")
async def get_ingest_status(
    course_id: str,
    request: Request,
    job_service: IngestionJobService = Depends(get_ingestion_job_service),
):
    user_id = request.state.user_id
    job = await job_service.get_job(user_id, course_id)
    if not job:
        return {"status": "none", "message": "No ingestion job found"}
    return job


@router.post("/ingest/sync")
async def sync_course(
    payload: IngestRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    ingestion_service: CourseIngestionService = Depends(get_course_ingestion_service),
    job_service: IngestionJobService = Depends(get_ingestion_job_service),
) -> dict:
    user_id = request.state.user_id
    
    await job_service.update_status(user_id, payload.course_id, "pending")
    
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


@router.delete("/ingest/{course_id}")
async def delete_index(
    course_id: str,
    request: Request,
    ingestion_service: CourseIngestionService = Depends(get_course_ingestion_service),
):
    user_id = request.state.user_id
    success = await ingestion_service.delete_course_index(user_id, course_id)
    return {"success": success, "course_id": course_id, "message": "Index completely wiped (including vectors)."}


@router.delete("/ingest/{course_id}/files/{filename}")
async def delete_file(
    course_id: str,
    filename: str,
    request: Request,
    ingestion_service: CourseIngestionService = Depends(get_course_ingestion_service),
):
    user_id = request.state.user_id
    result = await ingestion_service.delete_file_from_index(user_id, course_id, filename)
    return result


@router.get("/ingest/{course_id}/files")
async def list_ingested_files(
    course_id: str,
    request: Request,
    ingestion_service: CourseIngestionService = Depends(get_course_ingestion_service),
):
    user_id = request.state.user_id
    # We query the parent chunks collection for unique titles
    cursor = ingestion_service.db[ingestion_service.settings.mongo_parent_chunks_collection].aggregate([
        {"$match": {"user_id": user_id, "course_id": course_id}},
        {"$group": {
            "_id": "$metadata.title", 
            "total_chunks": {"$sum": 1},
            "source": {"$first": "$metadata.source"}
        }}
    ])
    files = await cursor.to_list(length=None)
    return [
        {
            "filename": f["_id"], 
            "chunk_count": f["total_chunks"],
            "source": f.get("source", "unknown")
        } for f in files
    ]


@router.post("/ingest/upload")
async def upload_local_file(
    request: Request,
    course_id: str,
    file: UploadFile = File(...),
    ingestion_service: CourseIngestionService = Depends(get_course_ingestion_service),
):
    user_id = request.state.user_id
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported currently")
        
    file_bytes = await file.read()
    try:
        # Local upload remains synchronous because it's usually just one file
        return await ingestion_service.ingest_local_document(
            user_id=user_id, course_id=course_id, filename=file.filename, file_bytes=file_bytes
        )
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error(f"Failed to ingest local file: {exc}")
        raise HTTPException(status_code=500, detail="Failed to parse binary document")
