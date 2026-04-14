import asyncio
import random
import logging
from typing import Any, Dict, List, Optional, Tuple

import gymnasium as gym
from gymnasium import spaces
import numpy as np

from app.agents.rag_agent import rag_agent_node
from app.agents.critic import critic_agent_node
from app.rl.benchmark_queries import BENCHMARK_QUERIES
from app.config import get_settings

logger = logging.getLogger(__name__)

class EduverseEnv(gym.Env):
    """
    OpenEnv-compatible Reinforcement Learning environment for EduVerse Agents.
    Standardizes the RAG-Evaluation loop into a Gymnasium interface.
    """
    
    def __init__(self, user_id: str = "test_user", course_id: str = "test_course", config: Dict[str, Any] = None, settings_override: Optional[Any] = None, **kwargs):
        super().__init__()
        self.user_id = user_id
        self.course_id = course_id
        self.config = config or {} # Contains DB and Sync Client
        self.settings = settings_override or get_settings()
        self.settings_override = settings_override # Store for node injection
        
        # State tracking
        self.current_query = None
        self.current_context = []
        self.cumulative_score = 0.0
        self.episode_count = 0
        self.performance_history = []
        self.current_feedback = []
        
        # Define Spaces (Simplification for text-based environments)
        # Observation is a dict containing the query, context, and historical performance
        self.observation_space = spaces.Dict({
            "query": spaces.Text(min_length=0, max_length=1000),
            "context": spaces.Sequence(spaces.Text(min_length=0, max_length=5000)),
            "last_score": spaces.Box(low=0, high=1, shape=(1,), dtype=np.float32),
            "avg_historical_score": spaces.Box(low=0, high=1, shape=(1,), dtype=np.float32),
            "critic_feedback": spaces.Sequence(spaces.Text(min_length=0, max_length=1000))
        })
        
        # Action space is the text response from the agent
        self.action_space = spaces.Text(min_length=0, max_length=10000)

    def _get_obs(self) -> Dict[str, Any]:
        avg_score = 0.0
        if self.performance_history:
            avg_score = sum(self.performance_history) / len(self.performance_history)
            
        last_score = self.performance_history[-1] if self.performance_history else 0.0
            
        return {
            "query": self.current_query["query"] if self.current_query else "",
            "context": [doc.get("content", "") for doc in self.current_context],
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
        
        # 1. Pick a random query
        self.current_query = random.choice(BENCHMARK_QUERIES)
        
        # 2. Run the RAG Agent Node to get context
        # We simulate the AgentState
        initial_state = {
            "user_id": self.user_id,
            "course_id": self.course_id,
            "original_query": self.current_query["query"],
            "messages": [],
            "task": self.current_query.get("task", "qa"),
            "difficulty": self.current_query.get("difficulty", "medium")
        }
        
        try:
            # We call the rag_agent_node directly, injecting settings_override if present
            node_config = self.config.copy()
            if self.settings_override:
                node_config["configurable"]["settings_override"] = self.settings_override
                
            rag_output = await rag_agent_node(initial_state, node_config)
            self.current_context = rag_output.get("context_docs", [])
        except Exception as e:
            logger.error(f"RAG Agent failed in RL reset: {e}")
            self.current_context = []
            
        self.current_feedback = []
        return self._get_obs(), {"info": "Reset complete"}

    async def astep(self, action: str) -> Tuple[Dict[str, Any], float, bool, bool, Dict[str, Any]]:
        """
        Takes the agent's text response (action) and evaluates it via the Critic.
        Returns (obs, reward, terminated, truncated, info).
        """
        # 1. Run the Critic Agent Node to evaluate the response
        critic_state = {
            "response_text": action,
            "context_docs": self.current_context
        }
        
        reward = 0.0
        try:
            critic_output = await critic_agent_node(critic_state, self.config)
            review = critic_output.get("critic_review", {})
            
            from app.rl.scoring import calculate_rl_reward
            reward = calculate_rl_reward(review, action)

        except Exception as e:
            logger.error(f"Critic Agent failed in RL step: {e}")
            reward = 0.0
            review = {}

        self.current_feedback = review.get("issues", [])
            
        # 3. Update scores and history
        self.performance_history.append(max(0.0, reward)) # Clamp for history display
        self.cumulative_score += reward
        self.episode_count += 1
        
        # 4. Prepare return
        obs = self._get_obs()
        terminated = True  # In this RAG loop, one step = one episode
        truncated = False
        
        return obs, reward, terminated, truncated, {"review": review}

    def reset(self, *args, **kwargs):
        """Synchronous wrapper (not recommended for async nodes)"""
        return asyncio.run(self.areset(*args, **kwargs))

    def step(self, *args, **kwargs):
        """Synchronous wrapper (not recommended for async nodes)"""
        return asyncio.run(self.astep(*args, **kwargs))
