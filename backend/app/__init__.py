"""
eovpanel — OpenVPN management panel.

The FastAPI application is created here and imported by main.py.
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import (
    APP_NAME,
    APP_VERSION,
    CORS_ALLOW_CREDENTIALS,
    CORS_ALLOW_HEADERS,
    CORS_ALLOW_METHODS,
    CORS_ORIGINS,
)
from app.logging_config import setup_logging
from app.routers.admins import router as admins_router
from app.routers.auth import router as auth_router
from app.routers.health import router as health_router
from app.routers.settings import router as settings_router
from app.routers.stats import router as stats_router
from app.routers.subscription import router as subscription_router
from app.routers.users import router as users_router


def create_app() -> FastAPI:
    application = FastAPI(
        title=APP_NAME,
        version=APP_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # --- Logging ---
    setup_logging()

    # --- CORS ---
    application.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=CORS_ALLOW_CREDENTIALS,
        allow_methods=CORS_ALLOW_METHODS,
        allow_headers=CORS_ALLOW_HEADERS,
    )

    # --- Exception handlers ---
    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        errors = {}
        for error in exc.errors():
            loc = error.get("loc", [])
            field = ".".join(str(part) for part in loc if part != "body")
            msg = error.get("msg", "Invalid value")
            errors[field] = msg
        return JSONResponse(status_code=422, content={"detail": errors})

    # --- Routers ---
    application.include_router(health_router)
    application.include_router(auth_router)
    application.include_router(admins_router)
    application.include_router(users_router)
    application.include_router(settings_router)
    application.include_router(stats_router)
    # Public subscription endpoint — mounted OUTSIDE /api prefix
    application.include_router(subscription_router)

    # --- Scheduler startup/shutdown ---
    @application.on_event("startup")
    def _start_scheduler():
        from app.db import SessionLocal
        from app.db.seed import seed_all
        from app.jobs import register_jobs, scheduler

        # Seed DB on startup (idempotent)
        db = SessionLocal()
        try:
            seed_all(db)
            db.commit()
        finally:
            db.close()

        register_jobs()
        scheduler.start()
        application.state.scheduler = scheduler

    @application.on_event("shutdown")
    def _stop_scheduler():
        import logging

        logger = logging.getLogger(__name__)
        scheduler = getattr(application.state, "scheduler", None)
        if scheduler is not None:
            scheduler.shutdown(wait=False)
            logger.info("Scheduler shut down.")

    return application


app = create_app()
