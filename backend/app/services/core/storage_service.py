"""
app/services/core/storage_service.py
──────────────────────────────────────
Cloud Storage Service — Cloudinary.

All user-uploaded documents are stored in Cloudinary under:
  eduverse/{user_id}/{course_id}/{filename}

Returns cloudinary://<public_id> as the storage reference,
which the ProxyService resolves to a signed CDN URL.
"""
from __future__ import annotations

import functools
import logging
from typing import Optional

import anyio
import cloudinary
import cloudinary.api
import cloudinary.uploader
import cloudinary.utils

from app.config import get_settings

logger = logging.getLogger(__name__)


def _configure_cloudinary(settings=None) -> None:
    """Idempotently configure Cloudinary SDK from settings."""
    s = settings or get_settings()
    cloudinary.config(
        cloud_name=s.cloudinary_cloud_name,
        api_key=s.cloudinary_api_key,
        api_secret=s.cloudinary_api_secret,
        secure=True,
    )


class StorageService:
    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        _configure_cloudinary(self.settings)

    def _public_id(self, user_id: str, course_id: str, filename: str) -> str:
        """Builds the Cloudinary public_id for a file."""
        folder = self.settings.cloudinary_folder
        safe_name = "".join([c for c in filename if c.isalnum() or c in (".", "_", "-")]).strip()
        return f"{folder}/{user_id}/{course_id}/{safe_name}"

    async def save_file(
        self, user_id: str, course_id: str, filename: str, content: bytes
    ) -> str:
        """Uploads file bytes to Cloudinary and returns a cloudinary:// reference."""
        public_id = self._public_id(user_id, course_id, filename)

        try:
            # Cloudinary SDK is synchronous — run in a thread to avoid blocking the event loop
            _upload = functools.partial(
                cloudinary.uploader.upload,
                content,
                public_id=public_id,
                resource_type="raw",
                overwrite=True,
                use_filename=False,
            )
            result = await anyio.to_thread.run_sync(_upload)
            logger.info("Cloudinary upload OK: %s", result.get("secure_url"))
            return f"cloudinary://{public_id}"
        except Exception as exc:
            logger.error("Cloudinary upload failed for %s: %s", filename, exc)
            raise

    def get_download_url(self, public_id: str) -> str:
        """Returns a signed Cloudinary CDN URL for a given public_id."""
        url, _ = cloudinary.utils.cloudinary_url(
            public_id,
            resource_type="raw",
            sign_url=True,
        )
        return url

    async def delete_course_data(self, user_id: str, course_id: str) -> bool:
        """Deletes all Cloudinary files for a specific user/course folder."""
        prefix = f"{self.settings.cloudinary_folder}/{user_id}/{course_id}"
        try:
            _delete = functools.partial(
                cloudinary.api.delete_resources_by_prefix, prefix, resource_type="raw"
            )
            await anyio.to_thread.run_sync(_delete)
            logger.info("Cloudinary folder wiped: %s", prefix)
            return True
        except Exception as exc:
            logger.warning("Cloudinary course wipe failed (%s): %s", prefix, exc)
            return False

    async def delete_user_data(self, user_id: str) -> bool:
        """Deletes ALL Cloudinary files for a user (used during deep wipe)."""
        prefix = f"{self.settings.cloudinary_folder}/{user_id}"
        try:
            _delete = functools.partial(
                cloudinary.api.delete_resources_by_prefix, prefix, resource_type="raw"
            )
            await anyio.to_thread.run_sync(_delete)
            logger.info("Cloudinary user folder wiped: %s", prefix)
            return True
        except Exception as exc:
            logger.warning("Cloudinary user wipe failed (%s): %s", prefix, exc)
            return False

    async def delete_file(self, user_id: str, course_id: str, filename: str) -> bool:
        """Deletes a single file from Cloudinary."""
        public_id = self._public_id(user_id, course_id, filename)
        try:
            _destroy = functools.partial(
                cloudinary.uploader.destroy, public_id, resource_type="raw"
            )
            await anyio.to_thread.run_sync(_destroy)
            logger.info("Cloudinary file deleted: %s", public_id)
            return True
        except Exception as exc:
            logger.warning("Cloudinary file delete failed (%s): %s", public_id, exc)
            return False


def get_storage_service() -> StorageService:
    return StorageService()


__all__ = ["StorageService", "get_storage_service"]
