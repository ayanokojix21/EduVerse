from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.services.training.rl_service import get_rl_service, RLService

async def AdminRequired(request: Request):
    """RBAC gate: only users with role='admin' can access protected endpoints."""
    if getattr(request.state, "user_role", "student") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can access Reinforcement Learning controls."
        )

router = APIRouter()

@router.get("/stats", summary="Fetch global Reinforcement Learning performance metrics")
async def get_rl_stats(service: RLService = Depends(get_rl_service)):
    """Unified RLAIF performance stats for the judge dashboard."""
    return await service.get_stats_overview()


@router.get("/models", summary="List all registered models in the registry")
async def list_models(
    limit: int = 50,
    service: RLService = Depends(get_rl_service)
):
    """Returns a list of all fine-tuned models, versions, and their statuses."""
    return await service.list_models(limit=limit)


@router.get("/episodes", summary="List recent RL trajectories")
async def list_rl_episodes(
    limit: int = 50, 
    service: RLService = Depends(get_rl_service),
    _ = Depends(AdminRequired)
):
    """List historical RL trajectories (Query-Response-Reward triplets)."""
    return await service.list_episodes(limit=limit)


@router.get("/dpo/export", summary="Export DPO preference pairs as downloadable JSONL")
async def export_dpo_pairs(service: RLService = Depends(get_rl_service), _ = Depends(AdminRequired)):
    """Streams all DPO preference pairs as a JSONL file stream."""
    rows = await service.export_dpo_jsonl()
    return StreamingResponse(
        (row for row in rows),
        media_type="application/x-ndjson",
        headers={
            "Content-Disposition": 'attachment; filename="eduverse_dpo_pairs.jsonl"',
            "X-Total-Pairs": str(len(rows)),
        },
    )


@router.get("/dashboard", summary="RLAIF Dashboard — aggregated metrics for the hackathon demo")
async def get_dashboard(service: RLService = Depends(get_rl_service)):
    """Powers the unified RLAIF analytics dashboard."""
    return await service.get_dashboard_metrics()


@router.post("/train/trigger", summary="Trigger the autonomous self-improvement pipeline")
async def trigger_training(service: RLService = Depends(get_rl_service), _ = Depends(AdminRequired)):
    """Manually kick off the autonomous Kaggle training loop."""
    return await service.trigger_autonomous_training()


@router.post("/train/distill", summary="Trigger the Shadow Auditor (Distillation) manually")
async def trigger_distillation(service: RLService = Depends(get_rl_service), _ = Depends(AdminRequired)):
    """Manually kick off the Teacher-Student distillation process."""
    return await service.trigger_shadow_distillation()


@router.get("/train/status", summary="Query the status of the current training run")
async def get_training_status(service: RLService = Depends(get_rl_service)):
    """Checks the live status of the autonomous training pipeline."""
    return await service.get_training_status()
