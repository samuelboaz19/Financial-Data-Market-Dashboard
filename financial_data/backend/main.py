"""
main.py

Application entrypoint. Keeps wiring-only logic here:
    - logging setup
    - CORS
    - DB pool lifecycle (startup/shutdown)
    - router registration

All actual logic lives in routes/ and services/, and all DB access
lives in database.py, so this file should rarely need to change while
using the app as a troubleshooting lab.
"""
from pathlib import Path
from fastapi.staticfiles import StaticFiles
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
from database import init_pool, close_pool
from routes import health, market

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up market-dashboard API")
    init_pool()
    yield
    logger.info("Shutting down market-dashboard API")
    close_pool()


app = FastAPI(
    title="Crypto / Time-Series Market Dashboard API",
    description=(
        "FastAPI backend for a TimescaleDB troubleshooting lab. "
        "Reads from existing crypto_ticks, crypto_assets and "
        "one_day_candle objects - does not own or create the schema."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    Last-resort safety net so an unexpected exception never returns a
    bare stack trace to the client, but always shows up loudly in logs.
    """
    logger.exception("Unhandled exception on %s %s", request.method, request.url)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


app.include_router(health.router)
app.include_router(market.router)



# Serve the frontend
BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

app.mount(
    "/",
    StaticFiles(directory=FRONTEND_DIR, html=True),
    name="frontend",
)