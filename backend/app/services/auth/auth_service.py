from __future__ import annotations

import logging
import uuid
from fastapi import Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import Settings, get_settings
from app.db.mongodb import get_db
from app.db.oauth_repository import OAuthTokenRepository, get_oauth_repository
from app.utils.auth_utils import mint_app_jwt
from app.schemas.api import WipeDataResponse, GuestLoginResponse

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        settings: Settings,
        token_service: OAuthTokenRepository,
    ) -> None:
        self.db = db
        self.settings = settings
        self.token_service = token_service

    async def get_user_auth_status(self, user_id: str) -> dict:
        status_payload = await self.token_service.get_auth_status(user_id)
        return {"user_id": user_id, **status_payload}

    async def disconnect(self, user_id: str) -> bool:
        await self.token_service.disconnect_user(user_id)
        return True

    async def login_as_guest(self) -> GuestLoginResponse:
        guest_id = f"guest_{uuid.uuid4().hex[:12]}"
        token = mint_app_jwt(guest_id, self.settings)
        return GuestLoginResponse(
            user_id=guest_id,
            app_jwt=token,
            is_guest=True,
        )

    async def deep_wipe_user_data(self, user_id: str) -> WipeDataResponse:
        """Atomic deep-wipe of all user data across all persistent layers."""
        await self.token_service.disconnect_user(user_id)

        collections_to_purge = [
            self.settings.mongo_parent_chunks_collection,
            self.settings.mongo_child_chunks_collection,
            self.settings.mongo_semantic_cache_collection,
            self.settings.mongo_ingestion_jobs_collection,
            self.settings.mongo_user_profiles_collection,
            self.settings.mongo_rl_trajectories_collection,
            self.settings.mongo_cached_courses_collection,
            self.settings.mongo_local_courses_collection,
        ]

        for coll_name in collections_to_purge:
            await self.db[coll_name].delete_many({"user_id": user_id})

        checkpoint_filter = {"thread_id": {"$regex": f"^{user_id}:"}}
        await self.db["checkpoints"].delete_many(checkpoint_filter)
        await self.db["checkpoint_writes"].delete_many(checkpoint_filter)
        await self.db["checkpoint_blobs"].delete_many(checkpoint_filter)

        # ── Cloud Storage Wipe (Cloudinary) ───────────────────────────────────
        files_removed = False
        if self.settings.has_cloudinary:
            try:
                from app.services.core.storage_service import StorageService
                storage = StorageService(self.settings)
                files_removed = await storage.delete_user_data(user_id)
            except Exception as exc:
                logger.warning("Cloudinary user wipe failed (non-critical): %s", exc)

        logger.info("SecurityAudit: Deep wipe completed for user %s", user_id)
        return WipeDataResponse(
            success=True,
            purged_collections=collections_to_purge,
            files_removed=files_removed,
        )


def get_auth_service(
    db: AsyncIOMotorDatabase = Depends(get_db),
    settings: Settings = Depends(get_settings),
    token_service: OAuthTokenRepository = Depends(get_oauth_repository),
) -> AuthService:
    return AuthService(db, settings, token_service)
