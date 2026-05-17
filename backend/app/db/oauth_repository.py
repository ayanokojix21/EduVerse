from __future__ import annotations

import logging
import asyncio
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from google.oauth2.credentials import Credentials

from app.config import Settings, get_settings
from app.db.mongodb import get_db
from app.schemas.db import OAuthTokenRecord
from app.utils.crypto import get_crypto_engine, CryptoEngine
from app.services.auth.google_service import GoogleAuthService

logger = logging.getLogger(__name__)

# Constants for OAuth assembly
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
GOOGLE_CLASSROOM_SCOPES = [
    "openid", "email", "profile",
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.me.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.students.readonly",
    "https://www.googleapis.com/auth/classroom.announcements.readonly",
    "https://www.googleapis.com/auth/classroom.courseworkmaterials.readonly",
    "https://www.googleapis.com/auth/drive.readonly"
]

class NeedsReauthError(Exception):
    """Raised when OAuth tokens are missing, expired, or revoked."""
    pass

class OAuthTokenRepository:
    """Data Access Layer for OAuth Credentials."""
    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        settings: Settings | None = None,
        crypto: CryptoEngine | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.collection = db[self.settings.mongo_oauth_tokens_collection]
        self.crypto = crypto or get_crypto_engine()
        self._refresh_locks: dict[str, asyncio.Lock] = {}

    def _get_user_lock(self, user_id: str) -> asyncio.Lock:
        """Returns (and creates if needed) a per-user async lock.
        
        Evicts the oldest entries when the dict exceeds 1000 entries to
        prevent unbounded memory growth in long-running production servers.
        """
        if user_id not in self._refresh_locks:
            # LRU-style eviction: drop oldest 200 entries when limit is hit
            if len(self._refresh_locks) >= 1000:
                evict_count = 200
                for old_key in list(self._refresh_locks.keys())[:evict_count]:
                    self._refresh_locks.pop(old_key, None)
            self._refresh_locks[user_id] = asyncio.Lock()
        return self._refresh_locks[user_id]

    async def upsert_tokens(
        self,
        user_id: str,
        email: str | None,
        access_token: str,
        refresh_token: str | None,
        token_expiry: datetime | None,
    ) -> None:
        """Saves encrypted tokens to MongoDB."""
        existing = await self.collection.find_one({"user_id": user_id})
        
        refresh_to_store = refresh_token
        if not refresh_to_store and existing:
            refresh_to_store = self.crypto.decrypt(existing.get("refresh_token"))

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        update_fields: dict[str, Any] = {
            "email": email,
            "access_token": self.crypto.encrypt(access_token),
            "needs_reauth": False,
            "needs_reauth_reason": None,
            "updated_at": now,
        }

        if token_expiry:
            update_fields["token_expiry"] = token_expiry.replace(tzinfo=None) if token_expiry.tzinfo else token_expiry
        if refresh_to_store:
            update_fields["refresh_token"] = self.crypto.encrypt(refresh_to_store)

        await self.collection.update_one(
            {"user_id": user_id},
            {"$set": update_fields, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )

    async def get_user_credentials(self, user_id: str) -> Credentials:
        """
        Retrieves and automatically refreshes Google Credentials.
        Orchestrates between Repository, Crypto, and GoogleService.
        """
        raw = await self.collection.find_one({"user_id": user_id})
        if not raw:
            raise NeedsReauthError("No tokens found")

        record = OAuthTokenRecord(**raw)
        if record.needs_reauth:
            raise NeedsReauthError(f"Re-auth required: {record.needs_reauth_reason}")

        access_token = self.crypto.decrypt(record.access_token)
        refresh_token = self.crypto.decrypt(record.refresh_token)
        
        creds = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri=GOOGLE_TOKEN_URI,
            client_id=self.settings.google_client_id,
            client_secret=self.settings.google_client_secret,
            scopes=GOOGLE_CLASSROOM_SCOPES,
            expiry=record.token_expiry,
        )

        if creds.expired:
            async with self._get_user_lock(user_id):
                fresh_raw = await self.collection.find_one({"user_id": user_id})
                if not fresh_raw:
                    raise NeedsReauthError("Token record vanished during refresh")
                fresh_record = OAuthTokenRecord(**fresh_raw)
                
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                if fresh_record.token_expiry and fresh_record.token_expiry > now:
                    fresh_access = self.crypto.decrypt(fresh_record.access_token)
                    fresh_refresh = self.crypto.decrypt(fresh_record.refresh_token)
                    return Credentials(
                        token=fresh_access,
                        refresh_token=fresh_refresh,
                        token_uri=GOOGLE_TOKEN_URI,
                        client_id=self.settings.google_client_id,
                        client_secret=self.settings.google_client_secret,
                        scopes=GOOGLE_CLASSROOM_SCOPES,
                        expiry=fresh_record.token_expiry,
                    )

                try:
                    await GoogleAuthService.refresh_credentials(creds)
                    await self.upsert_tokens(
                        user_id, record.email, creds.token, creds.refresh_token, creds.expiry
                    )
                except Exception as e:
                    await self.mark_needs_reauth(user_id, "refresh_failed")
                    raise NeedsReauthError("Token refresh failed") from e

        return creds

    async def mark_needs_reauth(self, user_id: str, reason: str) -> None:
        await self.collection.update_one(
            {"user_id": user_id},
            {"$set": {"needs_reauth": True, "needs_reauth_reason": reason, "updated_at": datetime.now(timezone.utc).replace(tzinfo=None)}}
        )

    async def get_auth_status(self, user_id: str) -> dict:
        """Returns a summary of the user's connection status."""
        raw = await self.collection.find_one({"user_id": user_id})
        if not raw:
            return {"google_connected": False, "needs_reauth": False}
        
        record = OAuthTokenRecord(**raw)
        return {
            "google_connected": True,
            "email": record.email,
            "needs_reauth": record.needs_reauth,
            "reauth_reason": record.needs_reauth_reason,
            "updated_at": record.updated_at
        }

    async def disconnect_user(self, user_id: str) -> None:
        """Revokes all tokens and purges record."""
        raw = await self.collection.find_one({"user_id": user_id})
        if raw:
            record = OAuthTokenRecord(**raw)
            for t_enc in [record.access_token, record.refresh_token]:
                token = self.crypto.decrypt(t_enc)
                if token:
                    await GoogleAuthService.revoke_token(token)
        
        await self.collection.delete_one({"user_id": user_id})

def get_oauth_repository(db=Depends(get_db)) -> OAuthTokenRepository:
    return OAuthTokenRepository(db)
