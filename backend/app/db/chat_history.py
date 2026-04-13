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

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ChatHistoryService:
    """CRUD operations for the chat_sessions collection."""

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
    ) -> None:
        """
        Append a message to an existing session, or create the session
        if it doesn't exist yet (upsert).

        The session title is auto-generated from the first user message.
        """
        now = _utc_now()
        message: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "role": role,
            "content": content,
            "timestamp": now.isoformat(),
        }
        if citations:
            from fastapi.encoders import jsonable_encoder
            message["citations"] = jsonable_encoder(citations)

        # Try to push onto existing session
        result = await self.collection.update_one(
            {"session_id": session_id, "user_id": user_id},
            {
                "$push": {"messages": message},
                "$inc": {"message_count": 1},
                "$set": {"updated_at": now},
            },
        )

        if result.matched_count == 0:
            # First message — create the session
            title = content[:60].strip() if role == "user" else "New Chat"
            await self.collection.insert_one({
                "session_id": session_id,
                "user_id": user_id,
                "course_id": course_id,
                "title": title,
                "messages": [message],
                "message_count": 1,
                "created_at": now,
                "updated_at": now,
            })
            logger.info("Created chat session %s for user %s", session_id, user_id[:8])

    async def list_sessions(
        self,
        user_id: str,
        course_id: str,
        limit: int = 50,
    ) -> list[dict]:
        """
        List chat sessions for a user + course, newest first.
        Returns lightweight summaries (no full message bodies).
        """
        cursor = self.collection.find(
            {"user_id": user_id, "course_id": course_id},
            {
                "_id": 0,
                "session_id": 1,
                "title": 1,
                "message_count": 1,
                "created_at": 1,
                "updated_at": 1,
            },
        ).sort("updated_at", -1).limit(limit)

        return await cursor.to_list(length=limit)

    async def get_session(
        self,
        session_id: str,
        user_id: str,
    ) -> dict | None:
        """Fetch a single session with full messages."""
        doc = await self.collection.find_one(
            {"session_id": session_id, "user_id": user_id},
            {"_id": 0},
        )
        return doc

    async def delete_session(
        self,
        session_id: str,
        user_id: str,
    ) -> bool:
        """Delete a session. Returns True if a doc was actually deleted."""
        result = await self.collection.delete_one(
            {"session_id": session_id, "user_id": user_id}
        )
        return result.deleted_count > 0

    async def update_title(
        self,
        session_id: str,
        user_id: str,
        title: str,
    ) -> bool:
        """Rename a session."""
        result = await self.collection.update_one(
            {"session_id": session_id, "user_id": user_id},
            {"$set": {"title": title, "updated_at": _utc_now()}},
        )
        return result.modified_count > 0
