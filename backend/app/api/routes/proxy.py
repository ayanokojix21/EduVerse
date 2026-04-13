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

    # 2. Fetch from Google
    async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
        headers = {"Authorization": f"Bearer {credentials.token}"}
        response = await client.get(target_url, headers=headers)

        if response.status_code != 200:
            return RedirectResponse(url=url)
        
    content_type = response.headers.get("Content-Type", "application/pdf")
    
    return Response(
        content=response.content,
        media_type=content_type,
        headers={
            "Content-Disposition": 'inline; filename="document"',
            "Accept-Ranges": "bytes"
        }
    )
