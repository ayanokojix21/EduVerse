from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.services.core.profile_service import get_profile_service, ProfileService
from app.schemas.api import ProfileResponse, KnowledgeUniverseResponse

router = APIRouter()

@router.get("/", response_model=ProfileResponse)
async def get_profile(
    request: Request,
    service: ProfileService = Depends(get_profile_service),
) -> ProfileResponse:
    """Fetches the user profile enriched with real-time document and session statistics."""
    return await service.get_enriched_profile(request.state.user_id)


@router.get("/mastery/universe", response_model=KnowledgeUniverseResponse)
async def get_mastery_universe(
    request: Request,
    service: ProfileService = Depends(get_profile_service),
) -> KnowledgeUniverseResponse:
    """
    Returns a D3-compatible Nodes & Links graph representing the user's 
    conceptual mastery across all course topics.
    """
    return await service.get_mastery_universe(request.state.user_id)
