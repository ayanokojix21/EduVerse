"""
app/services/kaggle_service.py
──────────────────────────────
Autonomous Kaggle Orchestrator.
Wraps the Kaggle CLI to trigger, poll, and download training artifacts.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from app.config import get_settings

logger = logging.getLogger(__name__)

class KaggleService:
    def __init__(self):
        self.settings = get_settings()
        self._ensure_kaggle_auth()

    def _ensure_kaggle_auth(self):
        """Prepares the kaggle.json file from environment variables if missing."""
        kaggle_dir = Path.home() / ".kaggle"
        config_file = kaggle_dir / "kaggle.json"
        
        if not config_file.exists() and self.settings.kaggle_key:
            kaggle_dir.mkdir(parents=True, exist_ok=True)
            auth_data = {
                "username": self.settings.kaggle_username,
                "key": self.settings.kaggle_key
            }
            with open(config_file, "w") as f:
                json.dump(auth_data, f)
            if os.name != 'nt':
                os.chmod(config_file, 0o600)
            logger.info("Kaggle authentication initialized.")

    def trigger_training(self, notebook_dir: str) -> bool:
        """
        Triggers a training run by pushing a code commit to Kaggle.
        Expects a 'kernel-metadata.json' to exist in the notebook_dir.
        """
        try:
            logger.info(f"Triggering Kaggle training in {notebook_dir}...")
            result = subprocess.run(
                ["kaggle", "kernels", "push", "-p", notebook_dir],
                capture_output=True,
                text=True,
                check=True
            )
            logger.info(f"Kaggle Push Success: {result.stdout.strip()}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Kaggle Push Failed: {e.stderr}")
            return False

    def get_status(self, kernel_id: str) -> str:
        """
        Queries the current status of the training kernel.
        Returns: 'running', 'complete', 'error', or 'unknown'.
        """
        try:
            result = subprocess.run(
                ["kaggle", "kernels", "status", kernel_id],
                capture_output=True,
                text=True,
                check=True
            )
            status_line = result.stdout.strip().lower()
            if "running" in status_line: return "running"
            if "complete" in status_line: return "complete"
            if "error" in status_line: return "error"
            return "unknown"
        except Exception as e:
            logger.error(f"Failed to check Kaggle status: {e}")
            return "unknown"

    def download_artifacts(self, kernel_id: str, download_path: str) -> List[str]:
        """
        Downloads all output files from the completed kernel.
        Returns a list of downloaded file paths.
        """
        try:
            Path(download_path).mkdir(parents=True, exist_ok=True)
            logger.info(f"Downloading artifacts from {kernel_id} to {download_path}...")
            
            subprocess.run(
                ["kaggle", "kernels", "output", kernel_id, "-p", download_path],
                check=True,
                capture_output=True
            )
            
            downloaded_files = [str(f) for f in Path(download_path).glob("*")]
            logger.info(f"Successfully downloaded {len(downloaded_files)} files.")
            return downloaded_files
        except subprocess.CalledProcessError as e:
            logger.error(f"Kaggle Download Failed: {e.stderr}")
            return []

    def create_metadata(self, notebook_dir: str, slug: str, title: str):
        """Generates the required kernel-metadata.json if missing."""
        meta_path = Path(notebook_dir) / "kernel-metadata.json"
        if not meta_path.exists():
            metadata = {
                "id": f"{self.settings.kaggle_username}/{slug}",
                "title": title,
                "code_file": "train_dpo.py",
                "language": "python",
                "kernel_type": "script",
                "is_private": "true",
                "enable_gpu": "true",
                "enable_internet": "true",
                "dataset_sources": [],
                "competition_sources": [],
                "kernel_sources": [],
                "model_sources": []
            }
            with open(meta_path, "w") as f:
                json.dump(metadata, f, indent=2)
            logger.info(f"Created Kaggle metadata in {notebook_dir}")
