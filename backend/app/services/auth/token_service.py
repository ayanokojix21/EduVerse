from __future__ import annotations

import logging
from fastapi import Depends

from app.config import Settings, get_settings
from app.db.oauth_repository import OAuthTokenRepository, get_oauth_repository
from app.utils.auth_utils import mint_app_jwt
from app.schemas.api import StoreTokensRequest, StoreTokensResponse

logger = logging.getLogger(__name__)

class TokenService:
    def __init__(
        self,
        token_repository: OAuthTokenRepository,
        settings: Settings,
    ) -> None:
        self.db_service = token_repository
        self.settings = settings

    async def handle_oauth_handshake(self, payload: StoreTokensRequest) -> StoreTokensResponse:
        """
        Processes the OAuth tokens from the frontend, encrypts them at rest,
        and mints a custom app-level JWT for the student.
        """
        await self.db_service.upsert_tokens(
            user_id=payload.user_id,
            email=str(payload.email) if payload.email else None,
            access_token=payload.access_token,
            refresh_token=payload.refresh_token,
            token_expiry=payload.token_expiry,
        )

        role = "student"
        if payload.email and payload.email in self.settings.admin_emails:
            role = "admin"
            logger.info("SecurityAudit: Admin role granted to %s", payload.email)

        app_jwt = mint_app_jwt(payload.user_id, self.settings, role=role)

        return StoreTokensResponse(
            stored=True,
            user_id=payload.user_id,
            app_jwt=app_jwt,
            needs_reauth=False,
        )


def get_token_service(
    token_repository: OAuthTokenRepository = Depends(get_oauth_repository),
    settings: Settings = Depends(get_settings),
) -> TokenService:
    return TokenService(token_repository, settings)
