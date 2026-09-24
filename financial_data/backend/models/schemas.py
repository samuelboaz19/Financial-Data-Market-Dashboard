"""
schemas.py

Pydantic models describing API request/response shapes. Kept separate
from routes and services so the "contract" of the API is easy to read
in one place.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# --- Health -----------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    service: str = "market-dashboard-api"


class DatabaseHealthResponse(BaseModel):
    status: str
    detail: Optional[str] = None
    latency_ms: Optional[float] = None


class TimescaleHealthResponse(BaseModel):
    status: str
    extension_installed: bool
    version: Optional[str] = None
    detail: Optional[str] = None


# --- Assets -------------------------------------------------------------

class Asset(BaseModel):
    symbol: str
    name: str


# --- Market data --------------------------------------------------------

class LatestMarketData(BaseModel):
    symbol: str
    latest_price: float
    latest_time: datetime
    latest_volume: Optional[float] = None
    previous_price: Optional[float] = None
    price_change: Optional[float] = None
    percent_change: Optional[float] = None


class Tick(BaseModel):
    time: datetime
    price: float
    day_volume: Optional[float] = None


class DailyCandle(BaseModel):
    bucket: datetime
    symbol: str
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    day_volume: Optional[float] = None
