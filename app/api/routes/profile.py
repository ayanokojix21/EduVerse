from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.db.profile_store import ProfileStore, get_profile_store

router = APIRouter()


@router.get("/profile")
async def get_profile(
    request: Request,
    profile_store: ProfileStore = Depends(get_profile_store),
) -> dict:
    """
    Return the student's adaptive-learning profile.

    Response::

        {
            "user_id":       str,
            "weak_topics":   list[str],
            "session_count": int,
        }

    ``weak_topics`` is updated after each chat session by the synthesizer
    node (via ``post_run_update``).  ``session_count`` is incremented at
    the end of every successful chat pipeline run.
    """
    user_id = request.state.user_id
    return await profile_store.get_profile(user_id)
