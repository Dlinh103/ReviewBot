"""GitHub App authentication and Installation Access Token management."""

import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
import jwt

from reviewbot.config import Settings, get_settings

logger = logging.getLogger("reviewbot.github.auth")


@dataclass
class CachedToken:
    """Cached installation access token."""

    token: str
    expires_at_epoch: float

    def is_valid(self, buffer_seconds: int = 300) -> bool:
        """Check if token is still valid with a safety buffer (default 5 minutes)."""
        return time.time() < (self.expires_at_epoch - buffer_seconds)


class GitHubAuthManager:
    """Manages GitHub App JWT creation and installation token caching."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._tokens_cache: dict[int, CachedToken] = {}

    def create_jwt(self, private_key_pem: str | None = None) -> str:
        """Generate a GitHub App JWT valid for up to 10 minutes."""
        app_id = self.settings.GITHUB_APP_ID
        if not app_id:
            raise ValueError("GITHUB_APP_ID is not configured")

        key_pem = private_key_pem or self.settings.get_private_key_content()
        if not key_pem:
            raise ValueError(
                f"GitHub App private key not found at {self.settings.GITHUB_APP_PRIVATE_KEY_PATH}"
            )

        now = int(time.time())
        payload = {
            # Issued at time (60 seconds in the past for clock drift)
            "iat": now - 60,
            # JWT expiration time (10 minute maximum)
            "exp": now + (9 * 60),
            # GitHub App's identifier
            "iss": app_id,
        }

        token = jwt.encode(payload, key_pem, algorithm="RS256")
        return token if isinstance(token, str) else token.decode("utf-8")

    async def get_installation_token(
        self,
        installation_id: int,
        client: httpx.AsyncClient | None = None,
        private_key_pem: str | None = None,
    ) -> str:
        """Fetch or return cached installation access token for given installation_id."""
        cached = self._tokens_cache.get(installation_id)
        if cached and cached.is_valid():
            return cached.token

        app_jwt = self.create_jwt(private_key_pem=private_key_pem)
        url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
        headers = {
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        should_close = False
        if client is None:
            client = httpx.AsyncClient(timeout=30.0)
            should_close = True

        try:
            response = await client.post(url, headers=headers)
            response.raise_for_status()
            data: dict[str, Any] = response.json()
        finally:
            if should_close:
                await client.aclose()

        token = data["token"]
        expires_at_str = data.get("expires_at")
        if expires_at_str:
            dt = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
            expires_at_epoch = dt.astimezone(UTC).timestamp()
        else:
            # Default fallback 1 hour
            expires_at_epoch = time.time() + 3600.0

        self._tokens_cache[installation_id] = CachedToken(
            token=token,
            expires_at_epoch=expires_at_epoch,
        )
        logger.info(
            "Acquired new installation token for installation_id=%s (expires in ~%ds)",
            installation_id,
            int(expires_at_epoch - time.time()),
        )
        return token
