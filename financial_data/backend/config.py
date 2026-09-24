"""
config.py

Centralised configuration for the backend.

Everything here is read from environment variables so that nothing
(especially DB credentials) is hard-coded. This file is intentionally
small and dependency-free so it is easy to reason about when
troubleshooting ("is the app even reading the env vars I set?").
"""

import os
from dotenv import load_dotenv

# Load a local .env file if present. In real deployments env vars are
# usually injected by the process manager / container / orchestrator,
# but .env makes local development easy.
load_dotenv()


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        raise ValueError(f"Environment variable {name}='{raw}' is not a valid integer")


class Settings:
    # --- Database connection -------------------------------------------------
    # NOTE: your TimescaleDB container exposes PostgreSQL on host port 5433,
    # while PostgreSQL *inside* the container listens on 5432. DB_PORT below
    # is the port the FastAPI process (running on your host, outside Docker)
    # should connect to -> 5433 by default.
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = _get_int("DB_PORT", 5433)
    DB_NAME: str = os.getenv("DB_NAME", "postgres")
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")

    # Connection pool sizing. Deliberately small defaults so that
    # "connection exhaustion" is easy to reproduce for lab exercises.
    DB_POOL_MIN_CONN: int = _get_int("DB_POOL_MIN_CONN", 1)
    DB_POOL_MAX_CONN: int = _get_int("DB_POOL_MAX_CONN", 10)

    # Timeouts (seconds). Useful when simulating slow / hanging queries.
    DB_CONNECT_TIMEOUT: int = _get_int("DB_CONNECT_TIMEOUT", 5)
    DB_STATEMENT_TIMEOUT_MS: int = _get_int("DB_STATEMENT_TIMEOUT_MS", 15000)

    # --- API -------------------------------------------------------------
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = _get_int("API_PORT", 8000)

    # Comma-separated list of allowed origins for CORS, e.g.
    # "http://localhost:5500,http://127.0.0.1:5500"
    CORS_ORIGINS: list[str] = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "*").split(",")
        if origin.strip()
    ]

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()
