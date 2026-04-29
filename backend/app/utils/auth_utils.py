from datetime import datetime, timedelta, timezone
from jose import jwt
from app.config import Settings

def mint_app_jwt(user_id: str, settings: Settings, role: str = "student") -> str:
    """Create a signed HS256 JWT for a user (Google sub or Guest ID)."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": user_id,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "iss": "eduverse-api",
        "aud": "eduverse-frontend",
        "typ": "JWT",
        "role": role,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
