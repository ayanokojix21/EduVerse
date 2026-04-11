"""
REST API routes for chat session management.

Routes
------
GET  /sessions?course_id=X       — list sessions for a course
GET  /sessions/{session_id}      — get full session with messages
DELETE /sessions/{session_id}    — delete a session
PATCH  /sessions/{session_id}    — rename a session
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from app.db.chat_history import ChatHistoryService
from app.db.mongodb import get_db

router = APIRouter()


def _get_service(db=Depends(get_db)) -> ChatHistoryService:
    return ChatHistoryService(db=db)


class RenameRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)


@router.get("/sessions")
async def list_sessions(
    request: Request,
    course_id: str = Query(..., min_length=1),
    service: ChatHistoryService = Depends(_get_service),
) -> list[dict]:
    """List all chat sessions for the authenticated user in a course."""
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Auth required")

    return await service.list_sessions(user_id=user_id, course_id=course_id)


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    request: Request,
    service: ChatHistoryService = Depends(_get_service),
) -> dict:
    """Get a single session with its full message history."""
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Auth required")

    session = await service.get_session(session_id=session_id, user_id=user_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return session


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    request: Request,
    service: ChatHistoryService = Depends(_get_service),
) -> dict:
    """Delete a chat session."""
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Auth required")

    deleted = await service.delete_session(session_id=session_id, user_id=user_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return {"deleted": True, "session_id": session_id}


@router.patch("/sessions/{session_id}")
async def rename_session(
    session_id: str,
    payload: RenameRequest,
    request: Request,
    service: ChatHistoryService = Depends(_get_service),
) -> dict:
    """Rename a chat session."""
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Auth required")

    updated = await service.update_title(session_id=session_id, user_id=user_id, title=payload.title)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return {"renamed": True, "session_id": session_id, "title": payload.title}
