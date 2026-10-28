"""CredenceIQ FastAPI application entry point."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from .config import settings
from .db import DatabaseQueryError, DatabaseUnavailable, pool
from .routers import applications, applicants, factors, health, overview, scoring

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s :: %(message)s",
)
logger = logging.getLogger("credenceiq")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "CredenceIQ API starting | exasol=%s:%s schema=%s pool=%s",
        settings.exasol_host,
        settings.exasol_port,
        settings.exasol_schema,
        settings.exasol_pool_size,
    )
    yield
    pool.close()
    logger.info("CredenceIQ API stopped")


app = FastAPI(
    title=settings.app_name,
    version=settings.api_version,
    description=(
        "Enterprise risk intelligence and automated adverse-action platform powered by "
        "Exasol Personal. All analytical endpoints execute live SQL."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list or ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Process-Time-Ms"],
)


@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000
    response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.2f}"
    if request.url.path.startswith("/api") and elapsed_ms > 2000:
        logger.warning("slow request %s %.0f ms", request.url.path, elapsed_ms)
    return response


@app.exception_handler(DatabaseUnavailable)
async def database_unavailable_handler(request: Request, exc: DatabaseUnavailable):
    logger.error("database unavailable: %s", exc)
    return JSONResponse(
        status_code=503,
        content={
            "detail": "Exasol is unavailable. Start the database and run the seed job.",
            "hint": "docker compose up -d exasol && python seed_data.py --if-empty",
        },
    )


@app.exception_handler(DatabaseQueryError)
async def database_query_handler(request: Request, exc: DatabaseQueryError):
    logger.error("database query failed: %s", exc)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "The analytical query failed.",
            "error": str(exc)[:600],
        },
    )


app.include_router(health.router, prefix="/api")
app.include_router(overview.router, prefix="/api")
app.include_router(applications.router, prefix="/api")
app.include_router(applicants.router, prefix="/api")
app.include_router(factors.router, prefix="/api")
app.include_router(scoring.router, prefix="/api")


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


@app.get("/api", include_in_schema=False)
def api_index() -> dict:
    return {
        "name": settings.app_name,
        "version": settings.api_version,
        "docs": "/docs",
        "endpoints": [
            "/api/overview",
            "/api/applications",
            "/api/applicant/{customer_id}/reconciliation",
            "/api/applicant/{customer_id}/adverse-action",
            "/api/applicant/{customer_id}/simulate",
            "/api/scoring/udf",
            "/api/factors",
            "/api/health",
        ],
    }
