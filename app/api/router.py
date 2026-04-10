from fastapi import APIRouter

from app.api.routes import auth, health, tokens

api_router = APIRouter()
api_router.include_router(auth.router,    tags=["auth"])
api_router.include_router(tokens.router,  tags=["auth"])
# api_router.include_router(courses.router, tags=["courses"])
# api_router.include_router(ingest.router,  tags=["ingestion"])
# api_router.include_router(cache.router,   tags=["cache"])
# api_router.include_router(profile.router, tags=["profile"])
api_router.include_router(health.router,  tags=["health"])
