import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase
from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

class RLStore:
    """
    Persistence layer for Reinforcement Learning trajectories.
    Stores 'episodes' from both synthetic training and live shadow auditing.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase, settings: Settings | None = None):
        self.settings = settings or get_settings()
        # We use a dedicated collection for RL monitoring
        self.collection = db["rl_episodes"]

    async def record_trajectory(
        self,
        user_id: str,
        session_id: str,
        query: str,
        response: str,
        reward: float,
        critic_review: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Saves a single RL episode/trajectory to the database."""
        try:
            doc = {
                "user_id": user_id,
                "session_id": session_id,
                "query": query,
                "response": response,
                "reward": float(reward),
                "review": critic_review,
                "metadata": metadata or {},
                "timestamp": datetime.now(timezone.utc)
            }
            result = await self.collection.insert_one(doc)
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Failed to record RL trajectory: {e}")
            return ""

    async def get_global_stats(self) -> Dict[str, Any]:
        """Calculates aggregated performance metrics across all recorded episodes."""
        try:
            pipeline = [
                {
                    "$group": {
                        "_id": None,
                        "avg_reward": {"$avg": "$reward"},
                        "total_episodes": {"$sum": 1},
                        "latest_timestamp": {"$max": "$timestamp"}
                    }
                }
            ]
            cursor = self.collection.aggregate(pipeline)
            results = await cursor.to_list(length=1)
            
            if not results:
                return {"avg_reward": 0.0, "total_episodes": 0}
                
            return {
                "avg_reward": round(results[0]["avg_reward"], 4),
                "total_episodes": results[0]["total_episodes"],
                "last_run": results[0]["latest_timestamp"]
            }
        except Exception as e:
            logger.error(f"Failed to fetch global RL stats: {e}")
            return {"error": str(e)}

    async def list_recent_episodes(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Fetches the latest trajectories for display or manual auditing."""
        cursor = self.collection.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit)
        return await cursor.to_list(length=limit)
