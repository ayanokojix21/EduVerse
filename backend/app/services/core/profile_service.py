from __future__ import annotations

import logging
from fastapi import Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import Settings, get_settings
from app.db.mongodb import get_db
from app.db.profile_repository import ProfileRepository, get_profile_repository
from app.schemas.api import ProfileResponse, KnowledgeUniverseResponse, MasteryNode, MasteryLink

logger = logging.getLogger(__name__)

class ProfileService:
    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        settings: Settings,
        profile_repo: ProfileRepository,
    ) -> None:
        self.db = db
        self.settings = settings
        self.profile_repo = profile_repo

    async def get_enriched_profile(self, user_id: str) -> ProfileResponse:
        """Fetches profile data and enriches it with real-time stats from MongoDB."""
        profile_data = await self.profile_repo.get_profile(user_id)
        profile_dict = profile_data.model_dump()
        
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {"_id": "$metadata.title"}}
        ]
        doc_results = await self.db[self.settings.mongo_parent_chunks_collection].aggregate(pipeline).to_list(length=None)
        
        session_count = await self.db[self.settings.mongo_chat_sessions_collection].count_documents({"user_id": user_id})
        
        return ProfileResponse(
            **profile_dict,
            total_documents=len(doc_results),
            actual_session_count=session_count
        )

    async def get_mastery_universe(self, user_id: str) -> KnowledgeUniverseResponse:
        """Generates a D3-compatible nodes/links graph of the user's topic mastery."""
        profile = await self.profile_repo.get_profile(user_id)
        mastery = profile.topic_mastery or {"Start Here": 0.5}
        
        PRE_REQS = {
            "Calculus": ["Algebra", "Geometry"],
            "Physics": ["Calculus", "Mathematics"],
            "Organic Chemistry": ["Chemistry", "Biology"],
            "Politics": ["History", "Law"],
            "Photosynthesis": ["Biology", "Botany"]
        }

        nodes = []
        links = []

        for topic, score in mastery.items():
            nodes.append(MasteryNode(
                id=topic,
                name=topic,
                val=10 + (score * 20),
                score=score,
                color="#4ade80" if score > 0.7 else ("#f87171" if score < 0.3 else "#fbbf24")
            ))
            
            if topic in PRE_REQS:
                for req in PRE_REQS[topic]:
                    if req in mastery:
                        links.append(MasteryLink(source=req, target=topic))

        return KnowledgeUniverseResponse(nodes=nodes, links=links)


def get_profile_service(
    db: AsyncIOMotorDatabase = Depends(get_db),
    settings: Settings = Depends(get_settings),
    profile_repo: ProfileRepository = Depends(get_profile_repository),
) -> ProfileService:
    return ProfileService(db, settings, profile_repo)
