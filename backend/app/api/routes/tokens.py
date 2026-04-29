from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.config import Settings, get_settings
from app.services.auth.token_service import get_token_service, TokenService
from app.schemas.api import StoreTokensRequest, StoreTokensResponse

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
