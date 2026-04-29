from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status, BackgroundTasks
from fastapi.responses import StreamingResponse

from app.db.mongodb import get_db, get_sync_client
from app.services.core.chat_service import ChatService
from app.schemas.api import ChatRequest

router = APIRouter()

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
