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

    try:
        credentials = await token_service.get_user_credentials(user_id)
    except NeedsReauthError:
        raise HTTPException(status_code=401, detail="Google authentication required")

    # 1. Identify if it's a Drive URL and extract ID
    match = DRIVE_ID_PATTERN.search(url)
    if not match:
        # Not a drive URL (e.g. YouTube, Classroom Link): Redirect them natively to it
        return RedirectResponse(url=url)

    file_id = match.group(1)
    target_url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
    headers = {"Authorization": f"Bearer {credentials.token}"}

    # 2. Stream from Google
    async def stream_from_google():
        async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
            async with client.stream("GET", target_url, headers=headers) as response:
                if response.status_code != 200:
                    # In a generator, we can't easily return a RedirectResponse here.
                    # We log it and stop. The client will see a partial/empty load.
                    logger.warning(f"Failed to stream PDF {file_id}: {response.status_code}")
                    return
                
                # Fetch essential headers from the Google response
                content_type = response.headers.get("Content-Type", "application/pdf")
                content_length = response.headers.get("Content-Length")
                
                async for chunk in response.aiter_bytes():
                    yield chunk

    from fastapi.responses import StreamingResponse
    
    return StreamingResponse(
        stream_from_google(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'inline; filename="document"',
            "Accept-Ranges": "bytes"
        }
    )
