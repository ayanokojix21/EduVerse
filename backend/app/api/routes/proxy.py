from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response

from app.services.core.proxy_service import get_proxy_service, ProxyService

router = APIRouter()

@router.get("/pdf")
async def proxy_pdf(
    url: str = Query(..., description="The direct Google Drive or local storage link"),
    request: Request = None,
    service: ProxyService = Depends(get_proxy_service),
) -> Response:
    """
    Securely proxies PDF content from Google Drive or local storage 
    to allow native browser features like jump-to-page (#page=N). 
    """
    return await service.get_pdf_response(url, request.state.user_id)
