from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.config import Settings, get_settings
from app.db.mongodb import get_db
from app.db.profile_store import ProfileStore, get_profile_store
from motor.motor_asyncio import AsyncIOMotorDatabase

router = APIRouter()


@router.get("/profile")
async def get_profile(
    request: Request,
    profile_store: ProfileStore = Depends(get_profile_store),
    db: AsyncIOMotorDatabase = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    user_id = request.state.user_id
    
    # 1. Get base profile
    profile = await profile_store.get_profile(user_id)
    
    # 2. Add Accurate Doc Count (Unique filenames across all courses)
    pipeline = [
        {"$match": {"user_id": user_id}},
        {"$group": {"_id": "$metadata.title"}}
    ]
    doc_results = await db[settings.mongo_parent_chunks_collection].aggregate(pipeline).to_list(length=None)
    profile["total_documents"] = len(doc_results)
    
    # 3. Add Accurate Session Count (Actual docs in chat_sessions)
    session_count = await db[settings.mongo_chat_sessions_collection].count_documents({"user_id": user_id})
    profile["actual_session_count"] = session_count
    
    return profile
