from fastapi import APIRouter

from app.api.routes import auth, chat, courses, health, ingestion, profile, sessions, tokens, proxy, rl, semantic_cache

api_router = APIRouter()

# Authentication & Identity
api_router.include_router(auth.router,    prefix="/auth", tags=["auth"])
api_router.include_router(tokens.router,  prefix="/auth", tags=["auth"])

# Core Features
api_router.include_router(courses.router, prefix="/courses", tags=["courses"])
api_router.include_router(chat.router,    prefix="/chat",    tags=["chat"])
api_router.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
api_router.include_router(profile.router, prefix="/profile", tags=["profile"])

# Specialized Services
api_router.include_router(ingestion.router, prefix="/ingestion", tags=["ingestion"])
api_router.include_router(proxy.router,     prefix="/proxy",     tags=["proxy"])
api_router.include_router(semantic_cache.router, prefix="/cache", tags=["cache"])
api_router.include_router(rl.router,        prefix="/rl",        tags=["rl"])

# System
api_router.include_router(health.router,  prefix="/health", tags=["health"])
