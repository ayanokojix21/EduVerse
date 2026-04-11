from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, status
from jose import jwt
from pydantic import BaseModel, EmailStr

from app.config import Settings, get_settings
from app.db.oauth_tokens import OAuthTokenService, get_oauth_token_service

router = APIRouter(prefix="/api")


async def verify_internal_secret(
    x_internal_secret: str | None = Header(default=None, alias="X-Internal-Secret"),
    settings: Settings = Depends(get_settings),
) -> None:
    """Dependency: rejects requests that don't carry the shared internal secret."""
    if not x_internal_secret or x_internal_secret != settings.internal_api_secret:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing or invalid internal secret",
        )


class StoreTokensRequest(BaseModel):
    """
    Sent by Next.js NextAuth jwt() callback after Google OAuth completes.

    The caller must include the header:
        X-Internal-Secret: <INTERNAL_API_SECRET>

    user_id is the Google account ``sub`` claim — included in the body
    because the user has no app JWT yet at the moment this is called.
    """

    user_id: str
    access_token: str
    refresh_token: str | None = None
    token_expiry: datetime | None = None
    email: EmailStr | None = None


class StoreTokensResponse(BaseModel):
    stored: bool
    user_id: str
    app_jwt: str          # signed JWT the frontend will store in the session
    needs_reauth: bool


def _mint_app_jwt(user_id: str, settings: Settings) -> str:
    """Create a signed HS256 JWT for the given Google sub (user_id)."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": user_id,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


@router.post(
    "/store-tokens",
    response_model=StoreTokensResponse,
    dependencies=[Depends(verify_internal_secret)],
)
async def store_tokens(
    payload: StoreTokensRequest,
    token_service: OAuthTokenService = Depends(get_oauth_token_service),
    settings: Settings = Depends(get_settings),
) -> StoreTokensResponse:
    """
    Store encrypted OAuth tokens in MongoDB and return a signed app JWT.

    Protected by the X-Internal-Secret header (shared secret between
    Next.js server and this backend). NOT protected by JWT middleware
    so NextAuth can call it before the session JWT exists.
    """
    # NOTE: Header validation is done in the route, not in middleware,
    # because this path is exempt from JWT middleware.
    # The caller must pass X-Internal-Secret.  We read it from the
    # request via a FastAPI dependency injected below via Headers.
    # To keep the signature simple we validate via a helper below.

    await token_service.upsert_tokens(
        user_id=payload.user_id,
        email=str(payload.email) if payload.email else None,
        access_token=payload.access_token,
        refresh_token=payload.refresh_token,
        token_expiry=payload.token_expiry,
    )

    app_jwt = _mint_app_jwt(payload.user_id, settings)

    return StoreTokensResponse(
        stored=True,
        user_id=payload.user_id,
        app_jwt=app_jwt,
        needs_reauth=False,
    )
