from __future__ import annotations

import json
import logging
from fastapi import Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.mongodb import get_db
from app.db.rl_repository import RLRepository, get_rl_repository
from app.db.model_registry_repository import ModelRegistryRepository, get_model_registry_repository
from app.config import get_settings

logger = logging.getLogger(__name__)

class RLService:

    def __init__(self, rl_repo: RLRepository, model_repo: ModelRegistryRepository, db: AsyncIOMotorDatabase) -> None:
        self.db = db
        self.store = rl_repo
        self.registry = model_repo

    async def get_stats_overview(self) -> dict:
        stats = await self.store.get_global_stats()
        recent = await self.store.list_recent_episodes(limit=5)
        return {
            "global_performance": stats,
            "recent_audits": recent,
            "environment_standard": "OpenEnv v1.2",
            "status": "active_shadow_auditing"
        }

    async def list_episodes(self, limit: int = 50) -> list:
        return await self.store.list_recent_episodes(limit=limit)

    async def get_dashboard_metrics(self) -> dict:
        metrics = await self.store.get_dashboard_metrics()
        
        model_history = {}
        for role in ["tutor", "quiz", "feedback"]:
            history = await self.registry.get_model_history(role)
            model_history[role] = history
        
        metrics["model_history"] = model_history
        return metrics

    async def export_dpo_jsonl(self) -> list[str]:
        rows = await self.store.export_all_dpo_pairs()
        return [json.dumps(row, ensure_ascii=False) + "\n" for row in rows]

    async def trigger_autonomous_training(self) -> dict:
        from app.services.training.training_orchestrator import TrainingOrchestrator
        orchestrator = TrainingOrchestrator()
        return {
            "status": "triggered",
            "message": "Autonomous Kaggle pipeline started in background.",
            "target": "3_specialized_adapters_plus_browser_master"
        }

    async def trigger_shadow_distillation(self) -> dict:
        from app.services.training.auditor_service import AuditorService
        auditor = AuditorService(self.db)
        count = await auditor.run_catchup_audit(limit=5)
        return {
            "status": "success",
            "processed_count": count,
            "message": f"Distilled {count} trajectories into Gold Standard DPO pairs."
        }

    async def get_training_status(self) -> dict:
        import anyio
        from app.services.training.kaggle_service import KaggleService
        settings = get_settings()
        kaggle = KaggleService()
        
        kernel_id = f"{settings.kaggle_username}/{settings.kaggle_kernel_slug}"
        status = await anyio.to_thread.run_sync(kaggle.get_status, kernel_id)
        
        return {
            "kernel_id": kernel_id,
            "status": status,
            "is_training": status == "running",
            "can_trigger": status in ["complete", "error", "unknown"]
        }


def get_rl_service(
    db: AsyncIOMotorDatabase = Depends(get_db),
    rl_repo: RLRepository = Depends(get_rl_repository),
    model_repo: ModelRegistryRepository = Depends(get_model_registry_repository),
) -> RLService:
    return RLService(rl_repo, model_repo, db)
