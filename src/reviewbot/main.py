"""FastAPI application entry point."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from reviewbot import __version__
from reviewbot.api.dashboard import router as dashboard_router
from reviewbot.api.health import router as health_router
from reviewbot.api.webhook import router as webhook_router
from reviewbot.config import get_settings

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("reviewbot")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager."""
    logger.info("Starting ReviewBot API in '%s' environment", settings.APP_ENV)
    yield
    logger.info("Shutting down ReviewBot API")


app = FastAPI(
    title="ReviewBot API",
    description="Automated AI Code Review Assistant for GitHub Pull Requests",
    version=__version__,
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(webhook_router)
app.include_router(dashboard_router)
