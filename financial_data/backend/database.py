"""
database.py

This is the ONLY file that knows how to open a connection to
PostgreSQL / TimescaleDB. Routes and services never call psycopg2
directly - they always go through get_connection() / get_cursor()
defined here.

Why this matters for the troubleshooting lab:
    - "database connection refused", "wrong credentials", "DNS failure",
      "port unavailable", "connection exhaustion" all surface here.
    - You can flip DB_HOST / DB_PORT / DB_USER / DB_PASSWORD in the
      environment and the failure will show up cleanly in this layer's
      logs, without any SQL-query logic getting in the way.
"""

import logging
from contextlib import contextmanager

import psycopg2
import psycopg2.pool
from psycopg2.extras import RealDictCursor

from config import settings

logger = logging.getLogger("database")

_pool: psycopg2.pool.SimpleConnectionPool | None = None


class DatabaseUnavailableError(Exception):
    """Raised when we cannot obtain a connection from the pool at all."""


def init_pool() -> None:
    """
    Create the connection pool. Called once at application startup.

    Deliberately NOT called at import time - this lets /health stay up
    even if the database is completely unreachable at boot, which is
    itself a useful state to be able to demonstrate.
    """
    global _pool
    if _pool is not None:
        return

    logger.info(
        "Initialising DB connection pool host=%s port=%s db=%s user=%s "
        "min_conn=%s max_conn=%s",
        settings.DB_HOST,
        settings.DB_PORT,
        settings.DB_NAME,
        settings.DB_USER,
        settings.DB_POOL_MIN_CONN,
        settings.DB_POOL_MAX_CONN,
    )
    try:
        _pool = psycopg2.pool.SimpleConnectionPool(
            settings.DB_POOL_MIN_CONN,
            settings.DB_POOL_MAX_CONN,
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            dbname=settings.DB_NAME,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            connect_timeout=settings.DB_CONNECT_TIMEOUT,
            options=f"-c statement_timeout={settings.DB_STATEMENT_TIMEOUT_MS}",
        )
        logger.info("DB connection pool created successfully")
    except psycopg2.OperationalError as exc:
        # This is the classic "refused / DNS failure / wrong port /
        # wrong credentials" failure mode. We log it clearly and let
        # the app continue starting up - health endpoints will report
        # the database as down rather than the whole process crashing.
        logger.error("Failed to initialise DB connection pool: %s", exc)
        _pool = None


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.closeall()
        logger.info("DB connection pool closed")
        _pool = None


@contextmanager
def get_connection():
    """
    Borrow a connection from the pool. Raises DatabaseUnavailableError
    (caught by routes and turned into a 503) if the pool doesn't exist
    or is exhausted / the DB is unreachable.
    """
    global _pool

    if _pool is None:
        # Pool was never created (DB was down at startup) - try again,
        # in case the database has since come back online.
        init_pool()

    if _pool is None:
        logger.error("get_connection() called but no DB pool is available")
        raise DatabaseUnavailableError("Database connection pool is not initialised")

    conn = None
    try:
        conn = _pool.getconn()
    except psycopg2.pool.PoolError as exc:
        # Pool exhausted (too many connections checked out) or pool closed.
        logger.error("Could not obtain a connection from the pool: %s", exc)
        raise DatabaseUnavailableError(str(exc)) from exc
    except psycopg2.OperationalError as exc:
        logger.error("Database is unreachable: %s", exc)
        raise DatabaseUnavailableError(str(exc)) from exc

    try:
        yield conn
    finally:
        if conn is not None:
            _pool.putconn(conn)


@contextmanager
def get_cursor(dict_cursor: bool = True):
    """
    Convenience wrapper that yields a cursor and commits/rolls back
    automatically. Almost all query code should use this rather than
    get_connection() directly.
    """
    with get_connection() as conn:
        cursor_factory = RealDictCursor if dict_cursor else None
        cur = conn.cursor(cursor_factory=cursor_factory)
        try:
            yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
