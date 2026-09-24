"""
market_service.py

All SQL that touches your existing TimescaleDB objects
(crypto_ticks, crypto_assets, one_day_candle) lives here, and ONLY
here. Routes call these functions; they never write SQL themselves.

This isolation matters for the lab: "slow query", "missing index",
"blocking query", "continuous aggregate not refreshing", "stale
dashboard data" are all things you can reproduce/diagnose by changing
queries in this one file without touching routing or connection code.
"""

import logging
from typing import Optional

import psycopg2

from database import get_cursor

logger = logging.getLogger("market_service")

# Allowed chart ranges -> SQL interval literals.
RANGE_TO_INTERVAL = {
    "1h": "1 hour",
    "6h": "6 hours",
    "24h": "24 hours",
    "7d": "7 days",
}


class InvalidSymbolError(Exception):
    """Raised when a symbol is not a known asset."""


class NoDataFoundError(Exception):
    """Raised when a query legitimately returns zero rows."""


def list_assets() -> list[dict]:
    query = "SELECT symbol, name FROM crypto_assets ORDER BY symbol;"
    with get_cursor() as cur:
        cur.execute(query)
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def _assert_known_symbol(cur, symbol: str) -> None:
    cur.execute("SELECT 1 FROM crypto_assets WHERE symbol = %s;", (symbol,))
    if cur.fetchone() is None:
        raise InvalidSymbolError(f"Unknown symbol: {symbol}")


def get_latest_market_data(symbol: str) -> dict:
    """
    Latest tick + previous tick for the given symbol from crypto_ticks,
    used to compute price change / percent change.
    """
    query = """
        SELECT "time", price, day_volume
        FROM crypto_ticks
        WHERE symbol = %s
        ORDER BY "time" DESC
        LIMIT 2;
    """
    with get_cursor() as cur:
        _assert_known_symbol(cur, symbol)
        cur.execute(query, (symbol,))
        rows = cur.fetchall()

    if not rows:
        raise NoDataFoundError(f"No tick data found for symbol: {symbol}")

    latest = rows[0]
    previous = rows[1] if len(rows) > 1 else None

    latest_price = float(latest["price"])
    previous_price = float(previous["price"]) if previous else None

    price_change = None
    percent_change = None
    if previous_price is not None:
        price_change = latest_price - previous_price
        if previous_price != 0:
            percent_change = (price_change / previous_price) * 100

    return {
        "symbol": symbol,
        "latest_price": latest_price,
        "latest_time": latest["time"],
        "latest_volume": float(latest["day_volume"]) if latest["day_volume"] is not None else None,
        "previous_price": previous_price,
        "price_change": price_change,
        "percent_change": percent_change,
    }


def get_ticks(symbol: str, range_key: str) -> list[dict]:
    if range_key not in RANGE_TO_INTERVAL:
        raise ValueError(
            f"Invalid range '{range_key}'. Valid options: {list(RANGE_TO_INTERVAL)}"
        )
    interval = RANGE_TO_INTERVAL[range_key]

    # interval comes only from our own whitelisted RANGE_TO_INTERVAL map
    # above (never directly from user input), so it's safe to interpolate.
    query = f"""
        SELECT "time", price, day_volume
        FROM crypto_ticks
        WHERE symbol = %s
          AND "time" >= NOW() - INTERVAL '{interval}'
        ORDER BY "time" ASC;
    """
    with get_cursor() as cur:
        _assert_known_symbol(cur, symbol)
        cur.execute(query, (symbol,))
        rows = cur.fetchall()

    return [dict(r) for r in rows]


def get_daily_candles(symbol: str, days: int = 14) -> list[dict]:
    query = """
        SELECT bucket, symbol, "open", high, low, "close", day_volume
        FROM one_day_candle
        WHERE symbol = %s
          AND bucket >= NOW() - (%s * INTERVAL '1 day')
        ORDER BY bucket ASC;
    """
    with get_cursor() as cur:
        _assert_known_symbol(cur, symbol)
        cur.execute(query, (symbol, days))
        rows = cur.fetchall()

    return [dict(r) for r in rows]


def get_latest_ingestion_timestamp() -> Optional[dict]:
    """
    Used by the system-status panel: what is the most recent row
    timestamp across all symbols, and how "stale" is it right now.
    """
    query = 'SELECT MAX("time") AS latest_time FROM crypto_ticks;'
    with get_cursor() as cur:
        cur.execute(query)
        row = cur.fetchone()
    if not row or row["latest_time"] is None:
        return None
    return {"latest_time": row["latest_time"]}
