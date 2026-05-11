from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status, BackgroundTasks
from fastapi.responses import StreamingResponse

from app.db.mongodb import get_db, get_sync_client
from app.services.core.chat_service import ChatService
from app.db.chat_repository import get_chat_repository, ChatRepository
from app.schemas.api import ChatRequest, ChatFeedbackRequest, HITLResumeRequest

router = APIRouter()

@router.post(
    "/{session_id}/messages/{message_id}/feedback",
    summary="Submit user feedback for an AI response",
)
async def submit_feedback(
    session_id: str,
    message_id: str,
    payload: ChatFeedbackRequest,
    request: Request,
    repo: ChatRepository = Depends(get_chat_repository),
):
    """Stores a thumbs up/down and optional comment for a specific message."""
    user_id: str = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    success = await repo.save_feedback(
        session_id=session_id,
        user_id=user_id,
        message_id=message_id,
        is_positive=payload.is_positive,
        comment=payload.comment
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Message or session not found")
        
    return {"success": True}


@router.post(
    "/stream",
    summary="Stream an AI tutoring response via SSE",
    response_description="text/event-stream with 7 event types",
)
async def chat_stream(
    payload: ChatRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
    sync_client=Depends(get_sync_client),
) -> StreamingResponse:
    """Main chat entry point. Orchestrates RAG and Agentic reasoning via ChatPipelineService."""
    user_id: str = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    pipeline = ChatService(db=db, sync_client=sync_client)
    
    return StreamingResponse(
        pipeline.run(
            user_id=user_id,
            course_id=payload.course_id,
            message=payload.message,
            background_tasks=background_tasks,
            session_id=payload.session_id,
            image_data=payload.image_data,
            image_mimetype=payload.image_mimetype,
        ),
        media_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control":      "no-cache",
            "X-Accel-Buffering":  "no",
            "Connection":         "keep-alive",
        },
    )


@router.post(
    "/stream/resume",
    summary="Resume a paused HITL graph after student makes a Socratic choice",
    response_description="text/event-stream — continues the interrupted RAG pipeline",
)
async def chat_resume(
    payload: HITLResumeRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
    sync_client=Depends(get_sync_client),
) -> StreamingResponse:
    """
    Resumes an interrupted LangGraph execution after a HITL pause.
    
    The frontend sends the student's decision ('search_web' | 'socratic_only')
    along with the session_id that uniquely identifies the paused thread.
    The graph picks up exactly where it left off, with the student's choice
    applied to the tutor_web_search_approved flag.
    """
    user_id: str = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    pipeline = ChatService(db=db, sync_client=sync_client)

    return StreamingResponse(
        pipeline.resume_run(
            session_id=payload.session_id,
            decision=payload.decision,
            user_id=user_id,
            background_tasks=background_tasks,
        ),
        media_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control":      "no-cache",
            "X-Accel-Buffering":  "no",
            "Connection":         "keep-alive",
        },
    )
