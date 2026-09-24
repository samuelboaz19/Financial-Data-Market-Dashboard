"""
routes/health.py

Three distinct health checks, deliberately kept separate so a failure
can be pinpointed to a specific layer:

    GET /health              -> is the FastAPI process up at all?
    GET /health/database     -> can we open a PostgreSQL connection?
    GET /health/timescaledb  -> is the timescaledb extension present?
"""

import logging
import time

from fastapi import APIRouter, HTTPException
import psycopg2

from database import get_cursor, DatabaseUnavailableError
from models.schemas import (
    HealthResponse,
    DatabaseHealthResponse,
    TimescaleHealthResponse,
)

logger = logging.getLogger("routes.health")

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """
    Pure liveness check - does NOT touch the database. If this
    endpoint is unreachable, the problem is the API process, DNS,
    the port, or the network path to it - not the database.
    """
    return HealthResponse(status="ok")


@router.get("/health/database", response_model=DatabaseHealthResponse)
def health_database() -> DatabaseHealthResponse:
    """
    Actually opens a connection and runs SELECT 1. This is the check
    that will surface: connection refused, wrong credentials, DNS
    failure, port unreachable, connection pool exhaustion, PostgreSQL
    unavailable.
    """
    start = time.perf_counter()
    try:
        with get_cursor() as cur:
            cur.execute("SELECT 1;")
            cur.fetchone()
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return DatabaseHealthResponse(status="connected", latency_ms=latency_ms)
    except DatabaseUnavailableError as exc:
        logger.error("Database health check failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=f"Database unavailable: {exc}",
        )
    except psycopg2.Error as exc:
        logger.error("Database health check failed with psycopg2 error: %s", exc)
        raise HTTPException(status_code=503, detail=f"Database error: {exc}")


@router.get("/health/timescaledb", response_model=TimescaleHealthResponse)
def health_timescaledb() -> TimescaleHealthResponse:
    """
    Confirms the timescaledb extension is installed and enabled in the
    connected database. This surfaces "wrong database connected to" or
    "extension not installed / TimescaleDB problem" style failures,
    separate from a plain PostgreSQL connectivity problem.
    """
    query = "SELECT extversion FROM pg_extension WHERE extname = 'timescaledb';"
    try:
        with get_cursor() as cur:
            cur.execute(query)
            row = cur.fetchone()
    except DatabaseUnavailableError as exc:
        logger.error("TimescaleDB health check failed - DB unavailable: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=f"Database unavailable: {exc}",
        )
    except psycopg2.Error as exc:
        logger.error("TimescaleDB health check failed with psycopg2 error: %s", exc)
        raise HTTPException(status_code=503, detail=f"Database error: {exc}")

    if row is None:
        logger.warning("timescaledb extension not found in connected database")
        return TimescaleHealthResponse(
            status="unavailable",
            extension_installed=False,
            detail="timescaledb extension is not installed in this database",
        )

    return TimescaleHealthResponse(
        status="connected",
        extension_installed=True,
        version=row["extversion"],
    )
