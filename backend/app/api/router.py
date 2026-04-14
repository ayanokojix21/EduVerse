from fastapi import APIRouter

from app.api.routes import auth, cache, chat, courses, health, ingest, profile, sessions, tokens, timetable, proxy, rl

api_router = APIRouter()
api_router.include_router(auth.router,    tags=["auth"])
api_router.include_router(tokens.router,  tags=["auth"])
api_router.include_router(courses.router, tags=["courses"])
api_router.include_router(ingest.router,  tags=["ingestion"])
api_router.include_router(proxy.router,   prefix="/proxy", tags=["proxy"])
api_router.include_router(cache.router,   tags=["cache"])
api_router.include_router(profile.router, tags=["profile"])
api_router.include_router(health.router,  tags=["health"])
api_router.include_router(chat.router,    tags=["chat"])
api_router.include_router(sessions.router, tags=["sessions"])
api_router.include_router(timetable.router, prefix="/timetable", tags=["timetable"])
api_router.include_router(rl.router, prefix="/rl", tags=["rl"])

