from __future__ import annotations

import logging
import httpx
import anyio
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials

from app.config import get_settings

logger = logging.getLogger(__name__)

GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_URI = "https://oauth2.googleapis.com/revoke"

class GoogleAuthService:
    """Orchestrates external interactions with the Google OAuth API."""

    @staticmethod
    async def refresh_credentials(credentials: Credentials) -> Credentials:
        """Triggers a synchronous Google refresh in a thread-safe async wrapper."""
        try:
            await anyio.to_thread.run_sync(credentials.refresh, GoogleRequest())
            return credentials
        except RefreshError as e:
            logger.error("Google token refresh failed: %s", e)
            raise

    @staticmethod
    async def revoke_token(token: str) -> bool:
        """Revokes an access or refresh token via Google's API."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(
                    GOOGLE_REVOKE_URI,
                    data={"token": token},
                )
                return response.status_code in (200, 400)
            except httpx.HTTPError as e:
                logger.warning("Failed to revoke Google token: %s", e)
                return False
