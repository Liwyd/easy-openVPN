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
from app.routers.admins import router as admins_router
from app.routers.auth import router as auth_router
from app.routers.health import router as health_router
from app.routers.users import router as users_router


def create_app() -> FastAPI:
    application = FastAPI(
        title=APP_NAME,
        version=APP_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
    )

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

    return application


app = create_app()
