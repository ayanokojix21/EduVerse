"""
app/db/model_registry.py
────────────────────────
Model Versioning & Registry.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.config import Settings, get_settings
from app.db.mongodb import get_db

logger = logging.getLogger(__name__)

class ModelRegistryRepository:
    """
    Persistence layer for training artifacts and model versioning.
    Used for 'Implicit Deployment'—routing traffic to the latest best weights.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.collection = db["model_registry"]
        self.runs_collection = db["training_runs"]

    async def get_current_model(self, role: str) -> str:
        """
        Returns the current stable model ID for a specific role (e.g. 'eduverse-rag:v5').
        If no fine-tuned model exists, returns the base model name from settings.
        """
        doc = await self.collection.find_one({"role": role, "status": "stable"})
        if not doc:
            settings = get_settings()
            model_map = {
                "orchestrator": settings.local_orchestrator_model,
                "tutor": settings.local_tutor_model,
                "quiz": settings.local_quiz_model,
                "feedback": settings.local_feedback_model,
                "critic": settings.local_critic_model,
            }
            return model_map.get(role, settings.local_tutor_model)
        
        return doc["model_id"]

    async def get_model_history(self, role: str) -> List[Dict[str, Any]]:
        """
        Returns the version history for a specific role (stable, legacy, candidate),
        including their eval scores and improvement deltas for the DPO dashboard.
        """
        cursor = self.collection.find(
            {"role": role},
            {"_id": 0}
        ).sort("version", -1)
        return await cursor.to_list(length=10)

    async def list_all_models(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Returns all registered models across all roles.
        """
        cursor = self.collection.find({}, {"_id": 0}).sort("registered_at", -1)
        return await cursor.to_list(length=limit)

    async def register_new_version(
        self,
        role: str,
        version: int,
        model_id: str,
        eval_score: float,
        improvement_delta: float,
        metadata: Dict[str, Any]
    ) -> None:
        """
        Registers a new version and marks it as 'candidate'.
        Promotion to 'stable' happens after Quality Gate validation.
        """
        doc = {
            "role": role,
            "version": version,
            "model_id": model_id,
            "eval_score": eval_score,
            "improvement_delta": improvement_delta,
            "status": "candidate",
            "metadata": metadata,
            "registered_at": datetime.now(timezone.utc)
        }
        await self.collection.insert_one(doc)

    async def promote_to_stable(self, role: str, model_id: str) -> None:
        """
        Atomically switches the 'stable' model for a specific role.
        Demotes previous stable versions to 'legacy'.
        """
        await self.collection.update_many(
            {"role": role, "status": "stable"},
            {"$set": {"status": "legacy", "demoted_at": datetime.now(timezone.utc)}}
        )
        await self.collection.update_one(
            {"role": role, "model_id": model_id},
            {"$set": {"status": "stable", "promoted_at": datetime.now(timezone.utc)}}
        )
        logger.info(f"Model PROMOTED: {role} -> {model_id}")

    async def log_training_run(self, run_data: Dict[str, Any]) -> str:
        """Logs a Kaggle training execution for audit trails."""
        run_data["timestamp"] = datetime.now(timezone.utc)
        result = await self.runs_collection.insert_one(run_data)
        return str(result.inserted_id)

    async def get_latest_master_url(self) -> Optional[str]:
        """Returns the download URL for the latest Browser Master model."""
        doc = await self.collection.find_one(
            {"role": "browser_master", "status": "stable"},
            sort=[("version", -1)]
        )
        return doc.get("metadata", {}).get("url") if doc else None
def get_model_registry_repository(db: AsyncIOMotorDatabase = Depends(get_db)) -> ModelRegistryRepository:
    return ModelRegistryRepository(db)
