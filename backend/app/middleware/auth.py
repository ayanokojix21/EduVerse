from collections.abc import Sequence

from fastapi import status
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

from app.config import get_settings

# Paths that bypass JWT verification entirely.
PUBLIC_PATH_PREFIXES = (
    "/",
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/auth/login/guest",
    "/auth/store-tokens",
    "/favicon.ico",
)


class JWTAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, public_paths: Sequence[str] | None = None) -> None:
        super().__init__(app)
        self.settings = get_settings()
        self.public_paths = tuple(public_paths or PUBLIC_PATH_PREFIXES)

    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path

        # Bypass JWT for all public paths.
        for pub in self.public_paths:
            if pub == "/":
                if path == "/":
                    return await call_next(request)
            elif path == pub or path.startswith(pub + "/"):
                return await call_next(request)

        authorization = request.headers.get("Authorization", "")
        token = None
        token_prefix = "Bearer "

        if authorization.startswith(token_prefix):
            token = authorization[len(token_prefix):]
        else:
            token = request.query_params.get("token")

        if not token:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Missing bearer token"},
            )


        try:
            payload = jwt.decode(
                token,
                self.settings.jwt_secret,
                algorithms=[self.settings.jwt_algorithm],
                audience="eduverse-frontend",
                issuer="eduverse-api",
            )
            
            if payload.get("typ") != "JWT":
                raise JWTError("Invalid token type")
                
            user_id = payload.get("sub")
            if not user_id:
                raise JWTError("JWT token missing sub claim")
        except JWTError:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid token"},
            )

        request.state.user_id = str(user_id)
        request.state.user_role = str(payload.get("role", "student"))
        return await call_next(request)
