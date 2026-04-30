from __future__ import annotations

import logging
from typing import Any

from app.config import get_settings, Settings
from app.db.chat_repository import ChatRepository
from app.db.profile_repository import ProfileRepository
from app.db.rl_repository import RLRepository

logger = logging.getLogger(__name__)

class AnalyticsService:
    def __init__(self, db, settings: Settings | None = None):
        self.db = db
        self.settings = settings or get_settings()

    async def process_post_run(
        self,
        user_id: str,
        session_id: str,
        course_id: str,
        query: str,
        final_state: dict[str, Any]
    ) -> None:
        """
        Main entry point for asynchronous post-run updates.
        Triggers history persistence, RL audits, and profile updates.
        """
        response = final_state.get("response_text", "")
        citations = final_state.get("citations", [])
        context_docs = final_state.get("context_docs", [])
        dpo_pairs = final_state.get("dpo_pairs", [])

        await self._update_user_profile(user_id, final_state)
        await self._persist_history(session_id, user_id, course_id, query, response, citations)
        await self._record_rl_trajectory(user_id, session_id, course_id, query, response, context_docs, final_state)
        await self._record_dpo(user_id, session_id, dpo_pairs, final_state)

    async def _update_user_profile(self, user_id: str, state: dict) -> None:
        try:
            store = ProfileRepository(db=self.db, settings=self.settings)
            await store.increment_session(user_id)

            new_topics = state.get("identified_weak_topics", [])
            critic = state.get("critic_review") or {}
            reward = state.get("reward", 0.5)

            topics_to_update = new_topics if new_topics else [state.get("original_query", "General")[:20]]

            if critic.get("severity") == "high":
                raw_issues = critic.get("issues") or []
                new_topics.extend([issue[:40].strip() for issue in raw_issues if issue])

            if new_topics:
                await store.update_weak_topics(user_id, new_topics)
            
            delta = 0.1 if reward > 0.7 else (-0.15 if reward < 0.4 else 0.0)
            if delta != 0:
                for topic in set(topics_to_update):
                    await store.update_topic_mastery(user_id, topic, delta)
                    
        except Exception as exc:
            logger.warning("Profile update failed: %s", exc)

    async def _persist_history(
        self, session_id: str, user_id: str, course_id: str, query: str, response: str, citations: list
    ) -> None:
        try:
            history = ChatRepository(db=self.db)
            await history.save_message(session_id, user_id, course_id, "user", query)
            await history.save_message(session_id, user_id, course_id, "assistant", response, citations=citations)
        except Exception as exc:
            logger.warning("History persistence failed: %s", exc)

    async def _record_rl_trajectory(
        self, user_id: str, session_id: str, course_id: str, query: str, response: str, docs: list, final_state: dict
    ) -> None:
        try:
            from app.rl.scoring import calculate_rl_reward
            
            review = final_state.get("critic_review", {})
            reward = calculate_rl_reward(review, response)
            
            store = RLRepository(db=self.db)
            await store.record_trajectory(user_id, session_id, query, response, reward, review, {"course_id": course_id, "mode": "shadow_audit"})
        except Exception as exc:
            logger.warning("RL audit failed: %s", exc)

    async def _record_dpo(self, user_id: str, session_id: str, pairs: list, state: dict) -> None:
        try:
            store = RLRepository(db=self.db)
            if pairs:
                await store.record_dpo_batch(user_id, session_id, pairs)
            
            trajectories = {
                "safety": state.get("safety_raw_responses", []),
                "tutor":  state.get("tutor_raw_responses", []),
                "quiz":   state.get("quiz_raw_responses", []),
                "feedback": state.get("feedback_raw_responses", [])
            }
            if any(trajectories.values()):
                await store.record_raw_trajectories(user_id, session_id, trajectories)
                
        except Exception as exc:
            logger.warning("DPO/Trajectory logging failed: %s", exc)
