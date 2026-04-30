import asyncio
import copy
import random
import logging
from typing import Any, Dict, List, Optional, Tuple

import gymnasium as gym
from gymnasium import spaces
import numpy as np

from app.agents.rag_subgraph import build_rag_subgraph
from app.agents.critic import critic_agent_node
from app.config import get_settings
import json
from pathlib import Path

logger = logging.getLogger(__name__)

BENCHMARK_PATH = Path(__file__).parent.parent / "services" / "training" / "kaggle_workspace" / "golden_benchmark.json"
try:
    with open(BENCHMARK_PATH, "r", encoding="utf-8") as f:
        _raw_data = json.load(f)
        GOLDEN_QUERIES = []
        for role, queries in _raw_data.items():
            for q in queries:
                GOLDEN_QUERIES.append({
                    "id": f"{role}_{len(GOLDEN_QUERIES)}",
                    "query": q,
                    "topic": role,
                    "difficulty": "hard"
                })
except Exception as e:
    logger.error(f"Failed to load Golden Benchmark in RL Env: {e}")
    GOLDEN_QUERIES = [{"query": "Explain the core concepts.", "topic": "fallback", "difficulty": "medium"}]



class EduverseEnv(gym.Env):
    """
    OpenEnv-compatible Reinforcement Learning environment for EduVerse Agents.
    Standardizes the RAG-Evaluation loop into a Gymnasium interface.
    """
    
    def __init__(self, user_id: str = "test_user", course_id: str = "test_course", config: Dict[str, Any] = None, settings_override: Optional[Any] = None, max_episode_steps: int = 50, **kwargs):
        super().__init__()
        self.user_id = user_id
        self.course_id = course_id
        self.config = config or {} 
        self.settings = settings_override or get_settings()
        self.settings_override = settings_override 
        self.max_episode_steps = max_episode_steps
        
        self.current_query = None
        self.current_context = []
        self.cumulative_score = 0.0
        self.episode_count = 0
        self.current_step = 0  
        self.performance_history = []
        self.current_feedback = []
        
        self.observation_space = spaces.Dict({
            "query": spaces.Text(min_length=0, max_length=1000),
            "context": spaces.Sequence(spaces.Text(min_length=0, max_length=5000)),
            "last_score": spaces.Box(low=0, high=1, shape=(1,), dtype=np.float32),
            "avg_historical_score": spaces.Box(low=0, high=1, shape=(1,), dtype=np.float32),
            "critic_feedback": spaces.Sequence(spaces.Text(min_length=0, max_length=1000))
        })
        
        self.action_space = spaces.Text(min_length=0, max_length=10000)

    def _get_obs(self) -> Dict[str, Any]:
        avg_score = 0.0
        if self.performance_history:
            avg_score = sum(self.performance_history) / len(self.performance_history)
            
        last_score = self.performance_history[-1] if self.performance_history else 0.0
            
        return {
            "query": self.current_query["query"] if self.current_query else "",
            "context": [
                {
                    "content": doc.get("content", ""),
                    "metadata": doc.get("metadata", {})
                } 
                for doc in self.current_context
            ],
            "last_score": float(last_score),
            "avg_historical_score": float(avg_score),
            "critic_feedback": self.current_feedback,
            "episode_steps": self.episode_count
        }

    @property
    def state(self) -> Dict[str, Any]:
        """Exposes complete internal state for OpenEnv logging."""
        return {
            "user_id": self.user_id,
            "course_id": self.course_id,
            "cumulative_score": self.cumulative_score,
            "episode_count": self.episode_count,
            "current_query": self.current_query,
            "history_len": len(self.performance_history)
        }

    async def areset(self, seed: Optional[int] = None, options: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Initialize the environment by fetching RAG context for a random benchmark query."""
        super().reset(seed=seed)
        
        self.current_query = copy.deepcopy(random.choice(GOLDEN_QUERIES))
        
        initial_state = {
            "user_id": self.user_id,
            "course_id": self.course_id,
            "original_query": "Identify top 3 concepts from document",
            "messages": [],
            "task": "rag",
            "difficulty": "medium"
        }
        
        try:
            rag_graph = build_rag_subgraph()
            node_config = self.config.copy()
            rag_output = await rag_graph.ainvoke(initial_state, node_config)
            self.current_context = rag_output.get("context_docs", [])
            
            if self.current_context:
                top_concept = self.current_context[0].get("metadata", {}).get("title", "this subject")
                self.current_query["query"] = self.current_query["query"].replace("'X'", top_concept).replace("X", top_concept)
                
        except Exception as e:
            logger.error(f"RAG Agent failed in RL reset: {e}")
            self.current_context = []
            
        self.current_feedback = []
        self.current_step = 0  
        return self._get_obs(), {"info": "Reset complete", "topic": self.current_query.get("topic")}

    async def astep(self, action: str) -> Tuple[Dict[str, Any], float, bool, bool, Dict[str, Any]]:
        """
        Takes the agent's text response (action) and evaluates it via the Critic.
        Returns (obs, reward, terminated, truncated, info).
        """
        critic_state = {
            "response_text": action,
            "context_docs": self.current_context
        }
        
        reward = 0.0
        try:
            critic_output = await critic_agent_node(critic_state, self.config)
            review = critic_output.update.get("critic_review", {})
            
            from app.rl.scoring import calculate_rl_reward
            reward = calculate_rl_reward(review, action)

        except Exception as e:
            logger.error(f"Critic Agent failed in RL step: {e}")
            reward = 0.0
            review = {}

        self.current_feedback = review.get("issues", [])
            
        reward = np.clip(reward, -2.5, 1.25)  
        self.performance_history.append(max(0.0, reward)) 
        self.cumulative_score += reward
        self.episode_count += 1
        self.current_step += 1
        
        obs = self._get_obs()
        terminated = True  
        truncated = self.current_step >= self.max_episode_steps  
        
        return obs, reward, terminated, truncated, {"review": review}

    def reset(self, *args, **kwargs):
        """Synchronous wrapper (not recommended for async nodes)"""
        return asyncio.run(self.areset(*args, **kwargs))

    def step(self, *args, **kwargs):
        """Synchronous wrapper (not recommended for async nodes)"""
        return asyncio.run(self.astep(*args, **kwargs))
