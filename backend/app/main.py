import os
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api import api_router
from app.config import get_settings
from app.db import mongo_lifespan
from app.middleware import JWTAuthMiddleware
from fastapi.security import HTTPBearer
from fastapi import Depends


def create_app(enable_db_lifespan: bool = True) -> FastAPI:
    settings = get_settings()
    lifespan = mongo_lifespan if enable_db_lifespan else None

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )

    # Added first = innermost (runs after CORS and GZip)
    app.add_middleware(JWTAuthMiddleware)

    # Added second = middle (compresses responses before they hit CORS)
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # Added last = outermost (catches every response, including 401s from JWT, to append CORS headers)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, dependencies=[Depends(HTTPBearer(auto_error=False, description="Enter your JWT generated from scripts/dev_jwt_generator.py"))])
    return app


app = create_app()
