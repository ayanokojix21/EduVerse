from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, Request, status

from app.services.auth.auth_service import get_auth_service, AuthService
from app.schemas.api import GuestLoginResponse, WipeDataResponse

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/status")
async def auth_status(
    request: Request,
    service: AuthService = Depends(get_auth_service),
) -> dict:
    """Returns the current authentication and sync status for the user."""
    return await service.get_user_auth_status(request.state.user_id)


@router.delete("/disconnect")
async def auth_disconnect(
    request: Request,
    service: AuthService = Depends(get_auth_service),
) -> dict:
    """Revokes tokens and disconnects Google Classroom."""
    await service.disconnect(request.state.user_id)
    return {"disconnected": True}


@router.post("/login/guest", response_model=GuestLoginResponse)
async def guest_login(
    service: AuthService = Depends(get_auth_service),
) -> GuestLoginResponse:
    """Generates a unique guest ID and returns a signed app JWT."""
    return await service.login_as_guest()


@router.post("/wipe", response_model=WipeDataResponse)
async def wipe_all_data(
    request: Request,
    service: AuthService = Depends(get_auth_service),
) -> WipeDataResponse:
    """Deep-cleans all data for the current user across all collections."""
    return await service.deep_wipe_user_data(request.state.user_id)
