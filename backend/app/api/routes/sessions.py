from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from app.services.core.session_service import get_session_service, SessionService
from app.schemas.api import RenameSessionRequest

router = APIRouter()

@router.get("/")
async def list_sessions(
    request: Request,
    course_id: str = Query(..., min_length=1),
    service: SessionService = Depends(get_session_service),
) -> list[dict]:
    """List all chat sessions for the authenticated user in a course."""
    return await service.list_user_sessions(request.state.user_id, course_id)


@router.get("/{session_id}")
async def get_session(
    session_id: str,
    request: Request,
    service: SessionService = Depends(get_session_service),
) -> dict:
    """Get a single session with its full message history."""
    return await service.get_session_detail(request.state.user_id, session_id)


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    request: Request,
    service: SessionService = Depends(get_session_service),
) -> dict:
    """Delete a chat session."""
    return await service.delete_user_session(request.state.user_id, session_id)


@router.patch("/{session_id}")
async def rename_session(
    session_id: str,
    payload: RenameSessionRequest,
    request: Request,
    service: SessionService = Depends(get_session_service),
) -> dict:
    """Rename a chat session."""
    return await service.rename_session(request.state.user_id, session_id, payload)
