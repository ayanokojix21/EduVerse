from __future__ import annotations

import os
import shutil
import logging
from pathlib import Path
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)

class StorageService:
    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        self.base_dir = Path(self.settings.upload_dir)
        self._ensure_base_dir()

    def _ensure_base_dir(self):
        """Creates the root upload directory if it doesn't exist."""
        if not self.base_dir.exists():
            self.base_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Initialized local storage root at {self.base_dir}")

    def get_user_course_dir(self, user_id: str, course_id: str) -> Path:
        """Returns the scoped directory for a specific user and course."""
        path = self.base_dir / user_id / course_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    async def save_file(self, user_id: str, course_id: str, filename: str, content: bytes) -> str:
        """Saves file bytes to disk and returns a local relative URL for the proxy."""
        target_dir = self.get_user_course_dir(user_id, course_id)
        safe_name = "".join([c for c in filename if c.isalnum() or c in (".", "_", "-")]).strip()
        file_path = target_dir / safe_name
        
        with open(file_path, "wb") as f:
            f.write(content)
        
        logger.info(f"Saved local file: {file_path}")
        return f"local://{user_id}/{course_id}/{safe_name}"

    def get_physical_path(self, user_id: str, course_id: str, filename: str) -> Optional[Path]:
        """Resolves a local storage link back to a physical file path."""
        path = self.base_dir / user_id / course_id / filename
        if path.exists():
            return path
        return None

    async def delete_course_data(self, user_id: str, course_id: str) -> bool:
        """Wipes all files for a specific course."""
        target_dir = self.base_dir / user_id / course_id
        if target_dir.exists():
            shutil.rmtree(target_dir)
            logger.info(f"Wiped local storage for course: {course_id}")
            return True
        return False

    async def delete_file(self, user_id: str, course_id: str, filename: str) -> bool:
        """Deletes a specific file from the local storage."""
        file_path = self.base_dir / user_id / course_id / filename
        if file_path.exists():
            file_path.unlink()
            logger.info(f"Deleted local file: {file_path}")
            return True
        return False

def get_storage_service():
    return StorageService()
    
__all__ = ["StorageService", "get_storage_service"]
