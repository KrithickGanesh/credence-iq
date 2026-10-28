"""System health and metadata endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from ..config import settings
from ..db import pool
from ..schemas import HealthResponse

router = APIRouter(tags=["system"])


@router.get("/live", summary="Liveness probe (does not touch Exasol)")
def live() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@router.get("/health", response_model=HealthResponse, summary="API and Exasol health")
def health() -> dict:
    database_up, ping_ms = pool.ping()
    exasol_version = None
    if database_up:
        try:
            with pool.acquire() as connection:
                version = connection.exasol_db_version
                exasol_version = str(version) if version else None
        except Exception:
            exasol_version = None
    return {
        "status": "ok" if database_up else "degraded",
        "database": "up" if database_up else "down",
        "schema": settings.exasol_schema,
        "api_version": settings.api_version,
        "exasol_version": exasol_version,
        "pool": pool.stats(),
        "ping_ms": ping_ms,
        "generated_at": datetime.now(timezone.utc),
    }
