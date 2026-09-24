"""
routes/market.py

HTTP layer for market data. Routes are deliberately thin: they parse
input, call services/market_service.py, and translate results/errors
into HTTP responses. No SQL lives here.

Symbol encoding note:
    Symbols like "BTC/USD" contain a slash, which doesn't play well as
    a raw path segment. The API accepts symbols with '-' in place of
    '/' in the URL (e.g. "BTC-USD") and converts internally. The
    frontend handles this conversion automatically - see frontend/app.js.
"""

import logging

from fastapi import APIRouter, HTTPException, Query
import psycopg2

from database import DatabaseUnavailableError
from models.schemas import Asset, LatestMarketData, Tick, DailyCandle
from services import market_service
from services.market_service import (
    InvalidSymbolError,
    NoDataFoundError,
    RANGE_TO_INTERVAL,
)

logger = logging.getLogger("routes.market")

router = APIRouter(prefix="/api", tags=["market"])


def _url_symbol_to_db_symbol(symbol: str) -> str:
    """'BTC-USD' -> 'BTC/USD'. Plain symbols like 'AAPL' pass through unchanged."""
    return symbol.replace("-", "/")


def _handle_db_errors(exc: Exception):
    """Shared translation of lower-layer exceptions into HTTPExceptions."""
    if isinstance(exc, InvalidSymbolError):
        logger.info("Invalid symbol requested: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, NoDataFoundError):
        logger.info("No data found: %s", exc)
        raise HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, DatabaseUnavailableError):
        logger.error("Database unavailable while serving request: %s", exc)
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}")
    if isinstance(exc, psycopg2.Error):
        logger.error("Unhandled database error: %s", exc)
        raise HTTPException(status_code=500, detail="Database query failed")
    # Unknown/unexpected error - log full detail server-side, return generic 500.
    logger.exception("Unexpected error while serving market request")
    raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/assets", response_model=list[Asset])
def get_assets():
    try:
        return market_service.list_assets()
    except Exception as exc:
        _handle_db_errors(exc)


@router.get("/market/{symbol}/latest", response_model=LatestMarketData)
def get_latest(symbol: str):
    db_symbol = _url_symbol_to_db_symbol(symbol)
    try:
        return market_service.get_latest_market_data(db_symbol)
    except Exception as exc:
        _handle_db_errors(exc)


@router.get("/market/{symbol}/ticks", response_model=list[Tick])
def get_ticks(
    symbol: str,
    range: str = Query(
        "1h",
        description=f"One of: {', '.join(RANGE_TO_INTERVAL.keys())}",
    ),
):
    db_symbol = _url_symbol_to_db_symbol(symbol)
    if range not in RANGE_TO_INTERVAL:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid range '{range}'. Valid options: {list(RANGE_TO_INTERVAL.keys())}",
        )
    try:
        return market_service.get_ticks(db_symbol, range)
    except Exception as exc:
        _handle_db_errors(exc)


@router.get("/market/{symbol}/daily", response_model=list[DailyCandle])
def get_daily(
    symbol: str,
    days: int = Query(14, ge=1, le=365, description="Number of days of candles to return"),
):
    db_symbol = _url_symbol_to_db_symbol(symbol)
    try:
        return market_service.get_daily_candles(db_symbol, days)
    except Exception as exc:
        _handle_db_errors(exc)
