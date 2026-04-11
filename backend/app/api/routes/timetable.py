from __future__ import annotations
import uuid
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.routes.chat import _run_pipeline
from app.db.mongodb import get_db

router = APIRouter()

class TimetableChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: str | None = Field(default=None)

@router.post("/stream")
async def timetable_stream(
    payload: TimetableChatRequest,
    request: Request,
    db=Depends(get_db),
) -> StreamingResponse:
    """
    Isolated SSE endpoint for the Timetable-only interface.
    """
    user_id: str = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    # 1. Force Isolation: Prefix session_id so it never clashing with main chat
    if not payload.session_id:
        session_id = f"timetable:{user_id}:{uuid.uuid4()}"
    else:
        # Ensure the user isn't trying to access a non-timetable session
        if not payload.session_id.startswith("timetable:"):
            session_id = f"timetable:{payload.session_id}"
        else:
            session_id = payload.session_id

    # 2. Re-use the main pipeline runner but pass "task='timetable'" to lock it
    return StreamingResponse(
        _run_pipeline(
            user_id=user_id,
            course_id="GLOBAL_TIMETABLE", 
            message=payload.message,
            db=db,
            session_id=session_id,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
