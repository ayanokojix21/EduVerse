from __future__ import annotations

import anyio
from fastapi import APIRouter, Depends, HTTPException, Request, status
from googleapiclient.errors import HttpError

from app.db.oauth_tokens import NeedsReauthError, OAuthTokenService, get_oauth_token_service
from app.services import list_courses

router = APIRouter()


@router.get("/courses")
async def get_courses(
    request: Request,
    token_service: OAuthTokenService = Depends(get_oauth_token_service),
) -> list[dict[str, str]]:
    user_id = request.state.user_id

    try:
        credentials = await token_service.get_user_credentials(user_id)
    except NeedsReauthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": str(exc), "needs_reauth": True},
        ) from exc

    try:
        return await anyio.to_thread.run_sync(list_courses, credentials)
    except HttpError as exc:
        status_code = getattr(exc, "status_code", None)
        if status_code is None:
            status_code = getattr(getattr(exc, "resp", None), "status", None)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Classroom API error ({status_code})",
        ) from exc
