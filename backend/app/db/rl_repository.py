import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.config import Settings, get_settings
from app.db.mongodb import get_db

logger = logging.getLogger(__name__)

class RLRepository:
    """
    Persistence layer for Reinforcement Learning trajectories.
    Stores 'episodes' from both synthetic training and live shadow auditing.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.collection = db["rl_episodes"]
        self.dpo_collection = db["rl_dpo_pairs"]
        self.trajectory_collection = db["rl_raw_trajectories"]

    async def record_dpo_batch(
        self,
        user_id: str,
        session_id: str,
        dpo_pairs: List[Dict[str, Any]]
    ) -> None:
        """Saves a batch of exact DPO (Prompt, Chosen, Rejected) pairs for HuggingFace trl."""
        if not dpo_pairs:
            return
            
        docs = []
        for pair in dpo_pairs:
            docs.append({
                "user_id": user_id,
                "session_id": session_id,
                "agent": pair.get("agent", "unknown"),
                "prompt": pair.get("prompt", ""),
                "chosen": pair.get("chosen", ""),
                "rejected": pair.get("rejected", ""),
                "critique": pair.get("critique", ""),
                "timestamp": datetime.now(timezone.utc)
            })
            
        try:
            await self.dpo_collection.insert_many(docs)
        except Exception as e:
            logger.error(f"Failed to record DPO batch: {e}")

    async def record_raw_trajectories(
        self,
        user_id: str,
        session_id: str,
        trajectories: Dict[str, List[str]]
    ) -> None:
        """Saves raw AIMessage contents for all agents (Safety, Tutor, Quiz, Feedback)."""
        try:
            doc = {
                "user_id": user_id,
                "session_id": session_id,
                "trajectories": trajectories,
                "timestamp": datetime.now(timezone.utc)
            }
            await self.trajectory_collection.insert_one(doc)
        except Exception as e:
            logger.error(f"Failed to record raw trajectories: {e}")

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

    # ── DPO Export & Dashboard ──────────────────────────────────

    async def export_all_dpo_pairs(self) -> List[Dict[str, Any]]:
        """
        Returns all DPO pairs in HuggingFace TRL-compatible format.
        
        Output schema per row:
            {
                "prompt": str,
                "chosen": str,
                "rejected": str,
                "agent": str,         # provenance metadata
                "critique": str,      # the Critic/Mentor's reasoning
                "timestamp": str      # ISO-8601 for audit trail
            }
        """
        try:
            cursor = self.dpo_collection.find(
                {},
                {
                    "_id": 0,
                    "prompt": 1,
                    "chosen": 1,
                    "rejected": 1,
                    "agent": 1,
                    "critique": 1,
                    "is_distilled": 1,
                    "timestamp": 1,
                },
            ).sort("timestamp", -1)
            rows = await cursor.to_list(length=None)
            for row in rows:
                if "timestamp" in row and hasattr(row["timestamp"], "isoformat"):
                    row["timestamp"] = row["timestamp"].isoformat()
            return rows
        except Exception as e:
            logger.error(f"Failed to export DPO pairs: {e}")
            return []

    async def get_dashboard_metrics(self) -> Dict[str, Any]:
        """
        Aggregates multi-dimensional hackathon dashboard metrics:
          1. Global RL stats (avg reward, episode count)
          2. DPO pair count per agent
          3. Critic pass/fail ratio from recent episodes
          4. Reward trend (last 20 episodes)
        """
        try:
            global_stats = await self.get_global_stats()

            dpo_pipeline = [
                {"$group": {
                    "_id": "$agent",
                    "count": {"$sum": 1},
                    "latest": {"$max": "$timestamp"},
                }},
                {"$sort": {"count": -1}},
            ]
            dpo_by_agent = await self.dpo_collection.aggregate(dpo_pipeline).to_list(length=50)
            total_dpo_pairs = sum(d["count"] for d in dpo_by_agent)

            critic_pipeline = [
                {"$sort": {"timestamp": -1}},
                {"$limit": 100},
                {"$group": {
                    "_id": None,
                    "total": {"$sum": 1},
                    "passed": {
                        "$sum": {"$cond": [{"$eq": ["$review.passed", True]}, 1, 0]}
                    },
                    "high_severity": {
                        "$sum": {"$cond": [{"$eq": ["$review.severity", "high"]}, 1, 0]}
                    },
                }},
            ]
            critic_results = await self.collection.aggregate(critic_pipeline).to_list(length=1)
            critic_stats = critic_results[0] if critic_results else {"total": 0, "passed": 0, "high_severity": 0}
            critic_stats.pop("_id", None)

            trend_cursor = self.collection.find(
                {}, {"_id": 0, "reward": 1, "timestamp": 1}
            ).sort("timestamp", -1).limit(20)
            trend_raw = await trend_cursor.to_list(length=20)
            reward_trend = [
                {
                    "reward": round(r["reward"], 4),
                    "timestamp": r["timestamp"].isoformat() if hasattr(r["timestamp"], "isoformat") else str(r["timestamp"]),
                }
                for r in reversed(trend_raw)
            ]

            return {
                "global_performance": global_stats,
                "dpo_pairs": {
                    "total": total_dpo_pairs,
                    "by_agent": [
                        {"agent": d["_id"], "count": d["count"]}
                        for d in dpo_by_agent
                    ],
                },
                "critic_quality": critic_stats,
                "reward_trend": reward_trend,
                "trajectories_count": await self.trajectory_collection.count_documents({}),
                "training_ready": total_dpo_pairs >= 10,
            }
        except Exception as e:
            logger.error(f"Dashboard metrics aggregation failed: {e}")
            return {"error": str(e)}

    # ── Teacher-Student Distillation ───────────────────────────

    async def list_pending_audits(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Finds local trajectories that haven't been audited by the Gemini Teacher yet."""
        filter_query = {
            "is_audited": {"$ne": True},
            "reward": {"$lt": 0.8}
        }
        cursor = self.collection.find(filter_query).sort("timestamp", -1).limit(limit)
        return await cursor.to_list(length=limit)

    async def record_teacher_distillation(
        self,
        episode_id: str,
        teacher_response: str,
        teacher_critique: str,
        agent_name: str = "distillation_teacher"
    ) -> None:
        """
        Marks an episode as audited and injects the 'Gold Standard' response 
        directly into the DPO preference store.
        """
        try:
            from bson import ObjectId
            episode = await self.collection.find_one({"_id": ObjectId(episode_id)})
            if not episode: return

            dpo_doc = {
                "user_id": episode["user_id"],
                "session_id": episode["session_id"],
                "agent": agent_name,
                "prompt": episode["query"],
                "chosen": teacher_response,
                "rejected": episode["response"],
                "critique": teacher_critique,
                "timestamp": datetime.now(timezone.utc),
                "is_distilled": True
            }
            await self.dpo_collection.insert_one(dpo_doc)

            await self.collection.update_one(
                {"_id": ObjectId(episode_id)},
                {"$set": {"is_audited": True, "distilled_at": datetime.now(timezone.utc)}}
            )
        except Exception as e:
            logger.error(f"Failed to record teacher distillation: {e}")
def get_rl_repository(db: AsyncIOMotorDatabase = Depends(get_db)) -> RLRepository:
    return RLRepository(db)