"""Health check endpoint."""

from fastapi import APIRouter

from reviewbot import __version__
from reviewbot.config import get_settings

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Liveness probe endpoint."""
    settings = get_settings()
    return {
        "status": "ok",
        "app": "reviewbot",
        "version": __version__,
        "environment": settings.APP_ENV,
    }
