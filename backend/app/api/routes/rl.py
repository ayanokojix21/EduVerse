from fastapi import APIRouter, Depends, Request
from app.db.mongodb import get_db
from app.db.rl_store import RLStore
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/stats", summary="Fetch global Reinforcement Learning performance metrics")
async def get_rl_stats(db=Depends(get_db)):
    """
    Returns aggregated RL rewards across all user interactions.
    Used for proving 'Live OpenEnv Auditing' to judges and admins.
    """
    store = RLStore(db)
    stats = await store.get_global_stats()
    recent = await store.list_recent_episodes(limit=5)
    
    return {
        "global_performance": stats,
        "recent_audits": recent,
        "environment_standard": "OpenEnv v1.2",
        "status": "active_shadow_auditing"
    }

@router.get("/episodes", summary="List recent RL trajectories")
async def list_rl_episodes(limit: int = 50, db=Depends(get_db)):
    """List historical RL trajectories (Query-Response-Reward triplets)."""
    store = RLStore(db)
    return await store.list_recent_episodes(limit=limit)
