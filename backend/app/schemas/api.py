from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr

# ── Course Schemas ────────────────────────────────────────────────────────────

class LocalCourseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None


class UnifiedCourse(BaseModel):
    id: str
    name: str
    source: str  
    description: str | None = None
    is_ingested: bool = False
    assignment_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None
    
    model_config = {"extra": "ignore"}


# ── Token & Auth Schemas ──────────────────────────────────────────────────────

class StoreTokensRequest(BaseModel):
    user_id: str
    access_token: str
    refresh_token: str | None = None
    token_expiry: datetime | None = None
    email: EmailStr | None = None


class StoreTokensResponse(BaseModel):
    stored: bool
    user_id: str
    app_jwt: str
    needs_reauth: bool


class GuestLoginResponse(BaseModel):
    user_id: str
    app_jwt: str
    is_guest: bool = True


class WipeDataResponse(BaseModel):
    success: bool
    purged_collections: list[str]
    files_removed: bool


# ── Ingestion Schemas ────────────────────────────────────────────────────────

class IngestRequest(BaseModel):
    course_id: str = Field(min_length=1)
    force_refresh: bool = False


class IngestedFile(BaseModel):
    filename: str
    chunk_count: int
    source: str = "unknown"

class CourseIngestionStatus(BaseModel):
    course_id: str
    status: str  
    progress: float = 0.0  # 0-100
    error: str | None = None

# ── Chat & Agent Schemas ─────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    course_id: str = Field(min_length=1)
    session_id: str | None = Field(default=None, description="Provide to resume a previous conversation")
    image_data: str | None = Field(default=None, description="Base64 encoded image for multimodal analysis")
    image_mimetype: str | None = Field(default="image/png")


class ChatFeedbackRequest(BaseModel):
    is_positive: bool
    comment: str | None = Field(default=None, max_length=1000)


class HITLResumeRequest(BaseModel):
    """
    Payload for resuming a paused HITL graph execution.
    
    Sent by the frontend when the student makes their Socratic choice
    after the RAG pipeline paused due to insufficient classroom materials.
    """
    session_id: str = Field(
        min_length=1,
        description="The session_id that identifies the paused LangGraph thread."
    )
    decision: str = Field(
        description="Student's choice: 'search_web' to approve web search, 'socratic_only' for course-only response.",
        pattern="^(search_web|socratic_only)$"
    )


# ── Profile & Mastery Schemas ───────────────────────────────────────────────

class ProfileResponse(BaseModel):
    user_id: str
    email: str | None = None
    full_name: str | None = None
    total_documents: int = 0
    actual_session_count: int = 0
    topic_mastery: dict[str, float] = {}
    
    model_config = {"extra": "ignore"}


class MasteryNode(BaseModel):
    id: str
    name: str
    val: float
    score: float
    color: str


class MasteryLink(BaseModel):
    source: str
    target: str


class KnowledgeUniverseResponse(BaseModel):
    nodes: list[MasteryNode]
    links: list[MasteryLink]


# ── Session Schemas ─────────────────────────────────────────────────────────

class RenameSessionRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
