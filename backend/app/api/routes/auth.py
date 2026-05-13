from __future__ import annotations

import base64
import json
import logging
import secrets
import urllib.parse
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, Request, Header, status, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse

from app.config import get_settings, Settings
from app.db.oauth_repository import GOOGLE_CLASSROOM_SCOPES, OAuthTokenRepository
from app.schemas.api import (
    GuestLoginResponse, 
    WipeDataResponse, 
    StoreTokensRequest, 
    StoreTokensResponse
)
from app.services.auth.auth_service import AuthService, get_auth_service
from app.services.auth.token_service import get_token_service, TokenService
from app.utils.auth_utils import mint_app_jwt

logger = logging.getLogger(__name__)
router = APIRouter()

async def verify_internal_secret(
    x_internal_secret: str | None = Header(default=None, alias="X-Internal-Secret"),
    settings: Settings = Depends(get_settings),
) -> None:
    """Dependency: rejects requests that don't carry the shared internal secret."""
    if not x_internal_secret or x_internal_secret != settings.internal_api_secret:
        logger.warning("SecurityAudit: Internal secret mismatch from host. Access denied.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing or invalid internal secret",
        )

# Exact URI registered in Google Cloud Console (URI 5).
_AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
_TOKEN_URI = "https://oauth2.googleapis.com/token"


# ── Standard Auth Routes ──────────────────────────────────────────────────────

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


# ── Google OAuth — Manual HTTP Flow (no PKCE, no stale state) ────────────────

@router.get("/login/google")
async def login_google():
    """
    Redirects to Google sign-in.
    Builds the auth URL manually so NO code_verifier/PKCE is generated.
    """
    settings = get_settings()
    state = secrets.token_urlsafe(32)
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": " ".join(GOOGLE_CLASSROOM_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    auth_url = _AUTH_URI + "?" + urllib.parse.urlencode(params)
    response = RedirectResponse(auth_url)
    response.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,
        secure=not settings.app_debug,
        max_age=600,
        samesite="lax",
    )
    return response


@router.get("/callback/google")
async def auth_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    service: AuthService = Depends(get_auth_service),
):
    """
    Google lands here after sign-in.
    Exchanges the code via raw HTTP POST (no PKCE/code_verifier needed).
    Returns an app JWT ready to use in /docs.
    """
    if error:
        return JSONResponse(
            status_code=400,
            content={"error": error, "detail": "Google denied the auth request."},
        )
    if not code:
        return JSONResponse(
            status_code=400,
            content={"error": "missing_code", "detail": "No authorization code in request."},
        )

    cookie_state = request.cookies.get("oauth_state")
    if not state or not cookie_state or state != cookie_state:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_state", "detail": "CSRF validation failed."},
        )

    settings = get_settings()

    # Raw token exchange — bypasses google_auth_oauthlib and PKCE entirely
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            _TOKEN_URI,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )

    if resp.status_code != 200:
        logger.error("Token exchange HTTP %s: %s", resp.status_code, resp.text)
        return JSONResponse(
            status_code=400,
            content={"error": "token_exchange_failed", "detail": resp.json()},
        )

    token_data = resp.json()
    access_token: str = token_data["access_token"]
    refresh_token: str | None = token_data.get("refresh_token")
    expires_in: int = token_data.get("expires_in", 3600)
    expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    # Decode id_token (JWT) to extract email — no verification needed locally
    user_id = None
    id_token_str: str = token_data.get("id_token", "")
    if id_token_str:
        try:
            payload_b64 = id_token_str.split(".")[1]
            # Add padding if needed
            payload_b64 += "=" * (-len(payload_b64) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
            user_id = payload.get("email")
        except Exception as exc:
            logger.warning("Could not decode id_token: %s", exc)

    if not user_id:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_token", "detail": "Could not extract email from Google identity."},
        )

    # service.token_service IS the OAuthTokenRepository
    repo: OAuthTokenRepository = service.token_service
    await repo.upsert_tokens(
        user_id=user_id,
        email=user_id,
        access_token=access_token,
        refresh_token=refresh_token,
        token_expiry=expiry,
    )

    user_role = "admin" if user_id in settings.admin_emails else "student"
    app_jwt = mint_app_jwt(user_id, settings, role=user_role)
    logger.info("Auth: Tokens stored for %s with role %s", user_id, user_role)

    # Redirect to frontend callback page with the JWT token
    frontend_callback = f"{settings.frontend_origin}/auth/callback?token={urllib.parse.quote(app_jwt)}"
    response = RedirectResponse(url=frontend_callback, status_code=302)
    response.delete_cookie("oauth_state")
    return response


@router.post(
    "/store-tokens",
    response_model=StoreTokensResponse,
    dependencies=[Depends(verify_internal_secret)],
)
async def store_tokens(
    payload: StoreTokensRequest,
    service: TokenService = Depends(get_token_service),
) -> StoreTokensResponse:
    """Store encrypted OAuth tokens in MongoDB and return a signed app JWT."""
    return await service.handle_oauth_handshake(payload)
