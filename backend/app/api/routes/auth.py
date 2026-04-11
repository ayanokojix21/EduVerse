from fastapi import APIRouter, Depends, Request

from app.db.oauth_tokens import OAuthTokenService, get_oauth_token_service

router = APIRouter(prefix="/auth")


@router.get("/status")
async def auth_status(
    request: Request,
    token_service: OAuthTokenService = Depends(get_oauth_token_service),
) -> dict[str, str | bool]:
    user_id = request.state.user_id
    status_payload = await token_service.get_auth_status(user_id)

    return {
        "user_id": user_id,
        **status_payload,
    }


@router.delete("/disconnect")
async def auth_disconnect(
    request: Request,
    token_service: OAuthTokenService = Depends(get_oauth_token_service),
) -> dict[str, bool]:
    user_id = request.state.user_id
    await token_service.disconnect_user(user_id)
    return {"disconnected": True}
