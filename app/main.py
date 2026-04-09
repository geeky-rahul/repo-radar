"""
Application entry point.
Creates the FastAPI app, registers routers, and wires lifecycle hooks.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.api.v1 import health, search
from app.core.config import get_settings
from app.core.exceptions import AppBaseException
from app.core.logging import configure_logging, get_logger
from app.services.cache import close_redis, get_redis

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logger.info("startup", env=settings.app_env, model=settings.llm_model)
    await get_redis()  # warm up connection pool
    yield
    logger.info("shutdown")
    await close_redis()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="GitHub Repository Search API",
        description=(
            "AI-powered GitHub repository search: converts natural language queries "
            "into structured GitHub searches and returns ranked results."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.app_debug else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global exception handler for AppBaseException subclasses
    @app.exception_handler(AppBaseException)
    async def app_exception_handler(request: Request, exc: AppBaseException) -> JSONResponse:
        logger.error("unhandled_app_exception", message=exc.message, details=exc.details)
        return JSONResponse(
            status_code=500,
            content={"error": {"code": type(exc).__name__, "message": exc.message, "details": exc.details}},
        )

    # Routers
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(search.router, prefix="/api/v1")

    # Static files
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

        @app.get("/")
        async def root():
            return FileResponse(static_dir / "index.html")

    return app


app = create_app()


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_debug,
        log_level=settings.log_level.lower(),
    )
