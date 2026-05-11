"""
Chat session persistence — stores conversation messages in MongoDB
so users can list past chats and resume them.

Each session document:
    {
        "session_id": "userId:courseId:uuid",
        "user_id": "...",
        "course_id": "...",
        "title": "First message preview...",
        "messages": [
            {"role": "user", "content": "...", "timestamp": "..."},
            {"role": "assistant", "content": "...", "timestamp": "...", "citations": [...]}
        ],
        "message_count": 2,
        "created_at": "...",
        "updated_at": "..."
    }
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import Settings, get_settings
from app.schemas.db import ChatMessage, ChatSession
from app.db.mongodb import get_db

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)

class ChatRepository:
    """
    Data Access Layer for Chat Sessions.
    Encapsulates all MongoDB logic for conversation persistence.
    """
    def __init__(self, db: AsyncIOMotorDatabase, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.collection = db[self.settings.mongo_chat_sessions_collection]

    async def save_message(
        self,
        session_id: str,
        user_id: str,
        course_id: str,
        role: str,
        content: str,
        citations: list[dict] | None = None,
    ) -> ChatMessage:
        """
        Atomic append of a message to a session. 
        Creates the session if it doesn't exist (Upsert).
        """
        from fastapi.encoders import jsonable_encoder
        now = _utc_now()
        message = ChatMessage(role=role, content=content, citations=jsonable_encoder(citations) if citations else None)
        
        result = await self.collection.update_one(
            {"session_id": session_id, "user_id": user_id},
            {
                "$push": {"messages": message.model_dump()},
                "$inc": {"message_count": 1},
                "$set": {"updated_at": now},
            },
        )

        if result.matched_count == 0:
            title = content[:60].strip() if role == "user" else "New Chat"
            session = ChatSession(
                session_id=session_id,
                user_id=user_id,
                course_id=course_id,
                title=title,
                messages=[message],
                message_count=1,
                created_at=now,
                updated_at=now
            )
            await self.collection.insert_one(session.model_dump())
            logger.info("Initialized new ChatSession: %s", session_id[:8])
        
        return message

    async def list_sessions(
        self,
        user_id: str,
        course_id: str,
        limit: int = 50,
    ) -> list[dict]:
        """Returns lightweight session summaries, sorted by last activity."""
        cursor = self.collection.find(
            {"user_id": user_id, "course_id": course_id},
            {"_id": 0, "session_id": 1, "title": 1, "message_count": 1, "created_at": 1, "updated_at": 1}
        ).sort("updated_at", -1).limit(limit)
        return await cursor.to_list(length=limit)

    async def get_session(self, session_id: str, user_id: str) -> ChatSession | None:
        """Retrieves a full session with complete message history."""
        doc = await self.collection.find_one({"session_id": session_id, "user_id": user_id}, {"_id": 0})
        return ChatSession(**doc) if doc else None

    async def update_title(self, session_id: str, user_id: str, title: str) -> bool:
        """Renames a chat session."""
        result = await self.collection.update_one(
            {"session_id": session_id, "user_id": user_id},
            {"$set": {"title": title, "updated_at": _utc_now()}},
        )
        return result.matched_count > 0

    async def delete_session(self, session_id: str, user_id: str) -> bool:
        """Hard-deletes a conversation session."""
        result = await self.collection.delete_one({"session_id": session_id, "user_id": user_id})
        return result.deleted_count > 0

    async def save_feedback(
        self, 
        session_id: str, 
        user_id: str, 
        message_id: str, 
        is_positive: bool,
        comment: str | None = None
    ) -> bool:
        """
        Attaches human feedback to a specific message in the session history.
        """
        result = await self.collection.update_one(
            {"session_id": session_id, "user_id": user_id},
            {
                "$set": {
                    "messages.$[msg].feedback": {
                        "is_positive": is_positive,
                        "comment": comment,
                        "timestamp": _utc_now().isoformat()
                    }
                }
            },
            array_filters=[{"msg.id": message_id}]
        )
        return result.modified_count > 0

def get_chat_repository(db=Depends(get_db)) -> ChatRepository:
    return ChatRepository(db)
