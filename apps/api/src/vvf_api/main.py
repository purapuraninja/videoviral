"""Application factory and root mounting for the VVF API."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from vvf_api.auth import router as auth_router
from vvf_api.routers import agents, health, render, research
from vvf_shared.config import get_settings
from vvf_shared.logging import configure_logging, get_logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    log = get_logger()
    log.info(f"VVF API starting in {settings.env} mode")
    yield
    log.info("VVF API shutting down")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Viral Video Factory API",
        version="0.1.0",
        docs_url="/docs",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth_router)
    app.include_router(health.router)
    app.include_router(research.router, prefix="/api/v1")
    app.include_router(render.router, prefix="/api/v1")
    app.include_router(agents.router, prefix="/api/v1")
    return app


app = create_app()


def main() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "vvf_api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.env == "development",
    )


if __name__ == "__main__":
    main()
