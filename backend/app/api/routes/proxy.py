from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response, RedirectResponse
import httpx
import re

from app.db.oauth_tokens import OAuthTokenService, get_oauth_token_service, NeedsReauthError

router = APIRouter()

# Regular expression to extract file ID from Google Drive links
DRIVE_ID_PATTERN = re.compile(r"/d/([a-zA-Z0-9_-]{25,})")

@router.get("/pdf")
async def proxy_pdf(
    url: str = Query(..., description="The direct Google Drive or Classroom file URL"),
    request: Request = None,
    token_service: OAuthTokenService = Depends(get_oauth_token_service),        
):
    """
    Securely proxies PDF content from Google Drive to allow native browser      
    features like jump-to-page (#page=N) which are blocked by the Drive viewer. 
    """
    user_id = request.state.user_id

    # 1. Identify URL type (Drive or Cloudinary)
    drive_match = DRIVE_ID_PATTERN.search(url)
    is_cloudinary = "res.cloudinary.com" in url

    if not drive_match and not is_cloudinary:
        # Not recognized for proxying, redirect natively
        return RedirectResponse(url=url)

    target_url = ""
    headers = {}

    if drive_match:
        try:
            credentials = await token_service.get_user_credentials(user_id)
        except NeedsReauthError:
            raise HTTPException(status_code=401, detail="Google authentication required")
        
        file_id = drive_match.group(1)
        target_url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
        headers = {"Authorization": f"Bearer {credentials.token}"}
    else:
        # It's Cloudinary, bypass auth and stream directly to override attachment disposition
        target_url = url

    # 2. Stream from source
    async def stream_from_source():
        async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
            async with client.stream("GET", target_url, headers=headers) as response:
                if response.status_code != 200:
                    import logging
                    logging.getLogger(__name__).warning(f"Failed to stream proxy document: {response.status_code}")
                    return
                
                # Fetch essential headers from the Google response
                content_type = response.headers.get("Content-Type", "application/pdf")
                content_length = response.headers.get("Content-Length")
                
                async for chunk in response.aiter_bytes():
                    yield chunk

    from fastapi.responses import StreamingResponse
    
    return StreamingResponse(
        stream_from_source(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'inline; filename="document.pdf"',
            "Accept-Ranges": "bytes"
        }
    )
