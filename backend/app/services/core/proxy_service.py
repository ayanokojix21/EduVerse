from __future__ import annotations

import httpx
import logging
import re
from fastapi import Depends, HTTPException
from fastapi.responses import Response, RedirectResponse, FileResponse, StreamingResponse

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
        """Securely proxies PDF content from Google Drive or local storage."""
        drive_match = DRIVE_ID_PATTERN.search(url)
        is_local = url.startswith("local://")

        if not drive_match and not is_local:
            return RedirectResponse(url=url)

        if is_local:
            return self._handle_local_proxy(url)

        return await self._handle_google_drive_proxy(drive_match.group(1), user_id)

    def _handle_local_proxy(self, url: str) -> FileResponse:
        try:
            parts = url.replace("local://", "").split("/")
            if len(parts) >= 3:
                f_user_id, f_course_id, f_filename = parts[0], parts[1], "/".join(parts[2:])
                physical_path = self.storage_service.get_physical_path(f_user_id, f_course_id, f_filename)
                
                if physical_path and physical_path.exists():
                    return FileResponse(
                        physical_path,
                        media_type="application/pdf",
                        filename=f_filename,
                        content_disposition_type="inline"
                    )
            
            raise HTTPException(status_code=404, detail="Local document not found")
        except HTTPException: raise
        except Exception as exc:
            logger.error("Local Proxy failed: %s", exc)
            raise HTTPException(status_code=500, detail="Failed to load local document")

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
                "Accept-Ranges": "bytes"
            }
        )


def get_proxy_service(
    token_service: OAuthTokenRepository = Depends(get_oauth_repository),
    storage_service: StorageService = Depends(get_storage_service),
) -> ProxyService:
    return ProxyService(token_service, storage_service)
