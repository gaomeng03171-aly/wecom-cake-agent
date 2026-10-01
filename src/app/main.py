from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request

from app import __version__
from app.api.activities import router as activities_router
from app.api.admin import router as admin_router
from app.api.outbox import router as outbox_router
from app.api.participants import router as participants_router
from app.api.proposals import router as proposals_router
from app.api.reminders import router as reminders_router
from app.api.wecom import router as wecom_router
from app.api.wecom_callback import router as wecom_callback_router
from app.config import get_settings
from app.db import init_db
from app.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    if settings.auto_create_tables:
        init_db()
    start_scheduler()
    yield
    stop_scheduler()


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version=__version__,
        lifespan=lifespan,
    )
    application.include_router(activities_router)
    application.include_router(admin_router)
    application.include_router(participants_router)
    application.include_router(proposals_router)
    application.include_router(outbox_router)
    application.include_router(reminders_router)
    application.include_router(wecom_router)
    application.include_router(wecom_callback_router)

    @application.middleware("http")
    async def add_request_id(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid4().hex
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @application.get("/health", tags=["system"])
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "app": settings.app_name,
            "environment": settings.app_env,
            "time": datetime.now(timezone.utc).isoformat(),
        }

    return application


app = create_app()
