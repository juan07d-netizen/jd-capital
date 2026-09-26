from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from .config import APP_NAME, APP_VERSION
from .db import init_db
from .routes.api import router as api_router
from .routes.auth import router as auth_router
from .routes.pages import router as pages_router
from .services.research import recover_research_jobs, shutdown_research
from .session_secret import get_session_secret


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    recover_research_jobs()
    yield
    shutdown_research()


def create_app() -> FastAPI:
    application = FastAPI(title=APP_NAME, version=APP_VERSION, lifespan=lifespan)
    application.add_middleware(SessionMiddleware, secret_key=get_session_secret(), https_only=False, same_site="lax", max_age=60 * 60 * 8)
    application.include_router(auth_router)
    application.include_router(pages_router)
    application.include_router(api_router)
    return application


app = create_app()
