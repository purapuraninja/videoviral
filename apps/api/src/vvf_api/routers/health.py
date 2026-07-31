"""Health and readiness probes."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness probe")
def health() -> dict:
    return {"status": "ok", "service": "vvf-api", "version": "0.1.0"}


@router.get("/healthz", include_in_schema=False)
def healthz() -> dict:
    return {"status": "ok"}
