import logging
from typing import Any, Dict, List, Optional
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from app.rl.eduverse_env import EduverseEnv
from app.db.mongodb import get_motor_client
from pymongo import MongoClient
from app.config import get_settings

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="EduVerse OpenEnv RL Server")

# ── State Management ─────────────────────────────────────────────────────────

# In a real OpenEnv setup, these might be managed per-session.
# For simplicity, we use a single global environment instance tied to a test user/course.
# You can extend this to support dynamic sessions if needed.

import gymnasium as gym
import app.rl as rl_env # Ensure registration is triggered

_ENV_INSTANCE: Optional[gym.Env] = None

def get_env() -> gym.Env:
    global _ENV_INSTANCE
    if _ENV_INSTANCE is None:
        settings = get_settings()
        motor_client = get_motor_client()
        sync_client = MongoClient(settings.mongo_uri)
        db = motor_client[settings.mongo_db_name]
        
        # OpenEnv Standard Configuration
        options = {
            "user_id": "nishchan",
            "course_id": "848260096170",
            "config": {
                "db": db,
                "mongo_client_sync": sync_client
            }
        }
        
        # The 'Less Custom' Way: Use Gymnasium Factory
        logger.info("Instantiating EduVerse RL Environment through Gymnasium Registry...")
        _ENV_INSTANCE = gym.make("EduVerse-v0", **options)
        
    return _ENV_INSTANCE

# ── Request/Response Schemas ────────────────────────────────────────────────

class StepRequest(BaseModel):
    action: str

class EnvResponse(BaseModel):
    observation: Dict[str, Any]
    reward: Optional[float] = None
    terminated: Optional[bool] = None
    truncated: Optional[bool] = None
    info: Dict[str, Any]

# ── Endpoints ───────────────────────────────────────────────────────────────

@app.post("/reset", response_model=EnvResponse)
async def reset_env():
    """Initialize the RL context and return the first observation."""
    env = get_env()
    obs, info = await env.areset()
    return {
        "observation": obs,
        "info": info
    }

@app.post("/step", response_model=EnvResponse)
async def step_env(request: StepRequest):
    """Execute one step in the environment."""
    env = get_env()
    obs, reward, terminated, truncated, info = await env.astep(request.action)
    return {
        "observation": obs,
        "reward": reward,
        "terminated": terminated,
        "truncated": truncated,
        "info": info
    }

@app.get("/state")
async def get_state():
    """Return the current performance state of the environment."""
    env = get_env()
    return {
        "cumulative_score": env.cumulative_score,
        "episode_count": env.episode_count,
        "avg_score": (env.cumulative_score / env.episode_count) if env.episode_count > 0 else 0
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
