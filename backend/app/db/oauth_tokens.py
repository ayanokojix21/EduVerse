from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import anyio
import httpx
from cryptography.fernet import Fernet
from fastapi import Depends
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import Settings, get_settings
from app.db.mongodb import get_db

GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_URI = "https://oauth2.googleapis.com/revoke"
GOOGLE_CLASSROOM_SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.me.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.students.readonly",
    "https://www.googleapis.com/auth/classroom.announcements.readonly",
    "https://www.googleapis.com/auth/classroom.courseworkmaterials.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


class NeedsReauthError(Exception):
    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


class OAuthTokenService:
    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.collection = db[self.settings.mongo_oauth_tokens_collection]
        self.fernet = Fernet(self.settings.fernet_key)

    def _encrypt(self, value: str) -> str:
        return self.fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def _decrypt(self, value: str | None) -> str | None:
        if not value:
            return None
        return self.fernet.decrypt(value.encode("utf-8")).decode("utf-8")

    async def upsert_tokens(
        self,
        user_id: str,
        email: str | None,
        access_token: str,
        refresh_token: str | None,
        token_expiry: datetime | None,
    ) -> None:
        existing = await self.collection.find_one({"user_id": user_id})

        refresh_to_store = refresh_token
        if not refresh_to_store and existing is not None:
            refresh_to_store = self._decrypt(existing.get("refresh_token"))

        now = _utc_now()
        update_fields: dict[str, Any] = {
            "email": email,
            "access_token": self._encrypt(access_token),
            "needs_reauth": False,
            "needs_reauth_reason": None,
            "updated_at": now,
        }

        normalized_expiry = _normalize_datetime(token_expiry)
        if normalized_expiry is not None:
            update_fields["token_expiry"] = normalized_expiry

        if refresh_to_store:
            update_fields["refresh_token"] = self._encrypt(refresh_to_store)

        await self.collection.update_one(
            {"user_id": user_id},
            {
                "$set": update_fields,
                "$setOnInsert": {
                    "created_at": now,
                },
            },
            upsert=True,
        )

    async def mark_needs_reauth(self, user_id: str, reason: str) -> None:
        await self.collection.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "needs_reauth": True,
                    "needs_reauth_reason": reason,
                    "updated_at": _utc_now(),
                }
            },
        )

    def _build_credentials(self, record: dict[str, Any]) -> Credentials:
        access_token = self._decrypt(record.get("access_token"))
        refresh_token = self._decrypt(record.get("refresh_token"))

        if not access_token:
            raise NeedsReauthError("Missing access token for user")

        return Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri=GOOGLE_TOKEN_URI,
            client_id=self.settings.google_client_id,
            client_secret=self.settings.google_client_secret,
            scopes=GOOGLE_CLASSROOM_SCOPES,
            expiry=_normalize_datetime(record.get("token_expiry")),
        )

    async def get_user_credentials(self, user_id: str) -> Credentials:
        record = await self.collection.find_one({"user_id": user_id})
        if record is None:
            raise NeedsReauthError("No OAuth tokens found for user")

        if record.get("needs_reauth"):
            raise NeedsReauthError("User must re-authenticate")

        credentials = self._build_credentials(record)

        if credentials.expired:
            if not credentials.refresh_token:
                await self.mark_needs_reauth(user_id, "missing_refresh_token")
                raise NeedsReauthError("Refresh token missing")

            if not self.settings.google_client_id or not self.settings.google_client_secret:
                await self.mark_needs_reauth(user_id, "missing_google_client_credentials")
                raise NeedsReauthError("Google client credentials are not configured")

            try:
                await anyio.to_thread.run_sync(credentials.refresh, GoogleRequest())
            except RefreshError as exc:
                await self.mark_needs_reauth(user_id, "refresh_failed")
                raise NeedsReauthError("OAuth refresh failed") from exc

            await self.collection.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "access_token": self._encrypt(credentials.token),
                        "token_expiry": _normalize_datetime(credentials.expiry),
                        "needs_reauth": False,
                        "needs_reauth_reason": None,
                        "updated_at": _utc_now(),
                    }
                },
            )

        return credentials

    async def get_auth_status(self, user_id: str) -> dict[str, bool]:
        record = await self.collection.find_one({"user_id": user_id})
        if record is None:
            return {
                "valid": False,
                "needs_reauth": True,
            }

        if record.get("needs_reauth"):
            return {
                "valid": False,
                "needs_reauth": True,
            }

        try:
            await self.get_user_credentials(user_id)
        except NeedsReauthError:
            return {
                "valid": False,
                "needs_reauth": True,
            }

        return {
            "valid": True,
            "needs_reauth": False,
        }

    async def disconnect_user(self, user_id: str) -> None:
        record = await self.collection.find_one({"user_id": user_id})

        if record is not None:
            access_token = self._decrypt(record.get("access_token"))
            refresh_token = self._decrypt(record.get("refresh_token"))

            for token in (access_token, refresh_token):
                if token:
                    await self._revoke_token(token)

        await self.collection.delete_one({"user_id": user_id})

    async def _revoke_token(self, token: str) -> None:
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(
                    GOOGLE_REVOKE_URI,
                    data={"token": token},
                )
                if response.status_code not in (200, 400):
                    response.raise_for_status()
            except httpx.HTTPError:
                return


def get_oauth_token_service(
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> OAuthTokenService:
    return OAuthTokenService(db=db)
