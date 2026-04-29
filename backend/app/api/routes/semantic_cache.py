from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.db.semantic_cache_repository import SemanticCacheRepository, get_semantic_cache_repository

router = APIRouter()


@router.delete("/{course_id}")
async def clear_semantic_cache(
    course_id: str,
    request: Request,
    semantic_cache_service: SemanticCacheRepository = Depends(get_semantic_cache_repository),
) -> dict[str, str | int]:
    user_id = request.state.user_id
    deleted = await semantic_cache_service.clear_course_cache(
        user_id=user_id,
        course_id=course_id,
    )

    return {
        "user_id": user_id,
        "course_id": course_id,
        "deleted": deleted,
    }
