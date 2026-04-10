from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.db.semantic_cache import SemanticCacheService, get_semantic_cache_service

router = APIRouter()


@router.delete("/cache/{course_id}")
async def clear_semantic_cache(
    course_id: str,
    request: Request,
    semantic_cache_service: SemanticCacheService = Depends(get_semantic_cache_service),
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
