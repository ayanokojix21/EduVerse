"""
app/services/core/proxy_service.py
────────────────────────────────────
Document Proxy Service — Cloud Native.

Handles two document sources:
  1. Google Drive  -> proxied via Bearer token stream
  2. Cloudinary    -> redirect to signed CDN URL (cloudinary:// scheme)
"""
from __future__ import annotations

import httpx
import logging
import re
from fastapi import Depends, HTTPException
from fastapi.responses import Response, RedirectResponse, StreamingResponse

from app.db.oauth_repository import OAuthTokenRepository, get_oauth_repository, NeedsReauthError
from app.services.core.storage_service import StorageService, get_storage_service

logger = logging.getLogger(__name__)

DRIVE_ID_PATTERN = re.compile(r"/d/([a-zA-Z0-9_-]{25,})")


class ProxyService:
    def __init__(
        self,
        token_service: OAuthTokenRepository,
        storage_service: StorageService,
    ) -> None:
        self.token_service = token_service
        self.storage_service = storage_service

    async def get_pdf_response(self, url: str, user_id: str) -> Response:
        """Routes PDF requests to Cloudinary CDN or Google Drive proxy."""
        drive_match = DRIVE_ID_PATTERN.search(url)
        is_cloudinary = url.startswith("cloudinary://")

        if is_cloudinary:
            return self._handle_cloudinary_redirect(url)

        if drive_match:
            return await self._handle_google_drive_proxy(drive_match.group(1), user_id)

        # Plain URL — redirect directly
        return RedirectResponse(url=url)

    def _handle_cloudinary_redirect(self, url: str) -> RedirectResponse:
        """Resolves a cloudinary:// reference to a signed CDN URL and redirects."""
        try:
            # Strip scheme: cloudinary://eduverse/user_id/course_id/filename
            public_id = url.replace("cloudinary://", "", 1)
            signed_url = self.storage_service.get_download_url(public_id)
            if not signed_url:
                raise HTTPException(status_code=404, detail="Cloudinary document not found")
            return RedirectResponse(url=signed_url, status_code=302)
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("Cloudinary proxy failed: %s", exc)
            raise HTTPException(status_code=500, detail="Failed to load cloud document")

    async def _handle_google_drive_proxy(self, file_id: str, user_id: str) -> StreamingResponse:
        try:
            credentials = await self.token_service.get_user_credentials(user_id)
        except NeedsReauthError:
            raise HTTPException(status_code=401, detail="Google authentication required")

        target_url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
        headers = {"Authorization": f"Bearer {credentials.token}"}

        async def stream_from_source():
            async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
                async with client.stream("GET", target_url, headers=headers) as response:
                    if response.status_code != 200:
                        logger.warning("Failed to stream proxy document: %s", response.status_code)
                        return
                    async for chunk in response.aiter_bytes():
                        yield chunk

        return StreamingResponse(
            stream_from_source(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": 'inline; filename="document.pdf"',
                "Accept-Ranges": "bytes",
            },
        )


def get_proxy_service(
    token_service: OAuthTokenRepository = Depends(get_oauth_repository),
    storage_service: StorageService = Depends(get_storage_service),
) -> ProxyService:
    return ProxyService(token_service, storage_service)
