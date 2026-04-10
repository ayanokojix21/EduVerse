from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.db.oauth_tokens import NeedsReauthError
from app.ingestion.pipeline import (
    ClassroomLoadError,
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
    ingestion_service: CourseIngestionService = Depends(get_course_ingestion_service),
) -> dict[str, int | bool | str]:
    user_id = request.state.user_id

    try:
        return await ingestion_service.ingest_course(
            user_id=user_id,
            course_id=payload.course_id,
            force_refresh=payload.force_refresh,
        )
    except NeedsReauthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": str(exc), "needs_reauth": True},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except ClassroomLoadError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
