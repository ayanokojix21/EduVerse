from collections.abc import Sequence

from fastapi import status
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

from app.config import get_settings

# Paths that bypass JWT verification entirely.
# /api/store-tokens is protected by INTERNAL_API_SECRET header instead.
PUBLIC_PATH_PREFIXES = (
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/api/store-tokens",
)


class JWTAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, public_paths: Sequence[str] | None = None) -> None:
        super().__init__(app)
        self.settings = get_settings()
        self.public_paths = tuple(public_paths or PUBLIC_PATH_PREFIXES)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Bypass JWT for all public paths (exact match or prefix match).
        for pub in self.public_paths:
            if path == pub or path.startswith(pub):
                return await call_next(request)

        authorization = request.headers.get("Authorization", "")
        token_prefix = "Bearer "

        if not authorization.startswith(token_prefix):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Missing bearer token"},
            )

        token = authorization[len(token_prefix):]

        try:
            payload = jwt.decode(
                token,
                self.settings.jwt_secret,
                algorithms=[self.settings.jwt_algorithm],
            )
            user_id = payload.get("sub")
            if not user_id:
                raise JWTError("JWT token missing sub claim")
        except JWTError:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid token"},
            )

        request.state.user_id = str(user_id)
        return await call_next(request)
