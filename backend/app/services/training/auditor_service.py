"""
app/services/shadow_auditor.py
──────────────────────────────
Teacher-Student Distillation Service.

Runs ASYNCHRONOUSLY in the background when internet is available.
Uses Gemini 2.5 Pro (Teacher) to generate gold-standard responses
for DPO preference learning. Never runs on the live student path.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import get_settings, Settings
from app.db.rl_repository import RLRepository, get_rl_repository
from app.utils.llm_pool import LLMFactory
from app.agents.prompts.teacher import TEACHER_PROMPT
from app.agents.schemas.teacher import TeacherAuditOutput

logger = logging.getLogger(__name__)

class AuditorService:
    def __init__(self, db: AsyncIOMotorDatabase, settings: Settings | None = None, rl_repo: RLRepository | None = None) -> None:
        self.settings = settings or get_settings()
        self.store = rl_repo or RLRepository(db, self.settings)

    async def run_catchup_audit(self, limit: int = 50) -> int:
        """
        Polls pending audits from local offline episodes and processes them
        via the Cloud Teacher (Gemini 2.5 Pro). This is the async distillation sync.
        """
        pending = await self.store.list_pending_audits(limit=limit)
        if not pending:
            return 0

        logger.info("Shadow Audit: Processing %d offline trajectories...", len(pending))

        teacher_llm = LLMFactory()._build_teacher_chain("tutor", temperature=0.7, schema=TeacherAuditOutput)

        count = 0
        for episode in pending:
            try:
                agent_name = episode.get("metadata", {}).get("agent", "rag_tutor")
                role_label = {
                    "rag_tutor": "RAG Tutor (Socratic)",
                    "quiz_drafter": "Quiz Drafter (Psychometric)",
                    "feedback_mentor": "Feedback Mentor (Growth Mindset RCA)",
                }.get(agent_name, "Universal Educational Agent")

                context_docs = episode.get("metadata", {}).get("context_docs", [])
                context_text = ""
                if context_docs:
                    context_text = "\n\n".join([f"Source {i+1}: {d.get('content', '')[:500]}" for i, d in enumerate(context_docs)])
                else:
                    context_text = "No context provided."

                prompt_messages = TEACHER_PROMPT.format_messages(
                    agent_role=role_label,
                    query=episode["query"],
                    context=context_text,
                    response=episode["response"],
                )

                res_raw = await teacher_llm.ainvoke(prompt_messages)
                
                if isinstance(res_raw, dict) and "parsed" in res_raw:
                    audit: TeacherAuditOutput = res_raw["parsed"]
                elif hasattr(res_raw, "parsed"): 
                    audit = res_raw.parsed
                else:
                    logger.warning("Teacher model returned non-structured output, skipping.")
                    continue

                gold_response = audit.gold_standard_response
                critique = audit.critique

                if not gold_response:
                    continue

                await self.store.record_teacher_distillation(
                    episode_id=str(episode["_id"]),
                    teacher_response=gold_response,
                    teacher_critique=critique,
                    agent_name=f"distilled_{agent_name}",
                )
                count += 1

                await asyncio.sleep(0.5)

            except Exception as exc:
                logger.error("Audit failed for episode %s: %s", episode["_id"], exc)

        logger.info("🥋 Shadow Audit Complete: %d DPO pairs ready.", count)
        return count
from fastapi import Depends
from app.db.mongodb import get_db

def get_auditor_service(
    db: AsyncIOMotorDatabase = Depends(get_db),
    rl_repo: RLRepository = Depends(get_rl_repository),
) -> AuditorService:
    return AuditorService(db=db, rl_repo=rl_repo)
