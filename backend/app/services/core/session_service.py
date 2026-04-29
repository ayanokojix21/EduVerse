from __future__ import annotations

import logging
from fastapi import Depends, HTTPException, status

from app.db.chat_repository import ChatRepository, get_chat_repository
from app.schemas.api import RenameSessionRequest

logger = logging.getLogger(__name__)

class SessionService:
    def __init__(self, db_service: ChatRepository) -> None:
        self.service = db_service

    async def list_user_sessions(self, user_id: str, course_id: str) -> list[dict]:
        return await self.service.list_sessions(user_id=user_id, course_id=course_id)

    async def get_session_detail(self, user_id: str, session_id: str) -> dict:
        session = await self.service.get_session(session_id=session_id, user_id=user_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        return session

    async def delete_user_session(self, user_id: str, session_id: str) -> dict:
        deleted = await self.service.delete_session(session_id=session_id, user_id=user_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        return {"deleted": True, "session_id": session_id}

    async def rename_session(self, user_id: str, session_id: str, payload: RenameSessionRequest) -> dict:
        updated = await self.service.update_title(session_id=session_id, user_id=user_id, title=payload.title)
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        return {"renamed": True, "session_id": session_id, "title": payload.title}


def get_session_service(db_repo: ChatRepository = Depends(get_chat_repository)) -> SessionService:
    return SessionService(db_repo)
