from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from pydantic import BaseModel, Field

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)

# ── Auth & Token Records ──────────────────────────────────────────────────────

class OAuthTokenRecord(BaseModel):
    """Strict schema for the OAuth tokens stored in MongoDB."""
    user_id: str
    email: str | None = None
    access_token: str
    refresh_token: str | None = None
    token_expiry: datetime | None = None
    needs_reauth: bool = False
    needs_reauth_reason: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"extra": "ignore"}


# ── Chat & Session Records ────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    role: str
    content: str
    timestamp: str = Field(default_factory=lambda: _utc_now().isoformat())
    citations: list[dict] | None = None

class ChatSession(BaseModel):
    session_id: str
    user_id: str
    course_id: str
    title: str
    messages: list[ChatMessage] = Field(default_factory=list)
    message_count: int = 0
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)


# ── Ingestion & Job Records ───────────────────────────────────────────────────

class IngestionJob(BaseModel):
    user_id: str
    course_id: str
    status: str = "pending"  
    error: Optional[str] = None
    last_updated: datetime = Field(default_factory=_utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ── Student Profile Records ───────────────────────────────────────────────────

class StudentProfile(BaseModel):
    user_id: str
    session_count: int = 0
    weak_topics: list[str] = Field(default_factory=list)
    topic_mastery: dict[str, float] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=_utc_now)
