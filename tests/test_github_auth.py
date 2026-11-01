"""Unit tests for GitHub App authentication and token management."""

import time

import jwt
import pytest
import respx
from httpx import Response

from reviewbot.config import Settings
from reviewbot.github.auth import GitHubAuthManager


def test_create_jwt_success(test_rsa_private_key_pem: str) -> None:
    settings = Settings(GITHUB_APP_ID="123456")
    manager = GitHubAuthManager(settings)

    token = manager.create_jwt(private_key_pem=test_rsa_private_key_pem)
    assert token is not None

    decoded = jwt.decode(
        token,
        options={"verify_signature": False},
    )
    assert decoded["iss"] == "123456"
    assert "iat" in decoded
    assert "exp" in decoded
    assert decoded["exp"] > decoded["iat"]


def test_create_jwt_missing_app_id() -> None:
    settings = Settings(GITHUB_APP_ID="")
    manager = GitHubAuthManager(settings)
    with pytest.raises(ValueError, match="GITHUB_APP_ID is not configured"):
        manager.create_jwt()


def test_create_jwt_missing_private_key() -> None:
    settings = Settings(
        GITHUB_APP_ID="123456",
        GITHUB_APP_PRIVATE_KEY_PATH="./non_existent_key.pem",
    )
    manager = GitHubAuthManager(settings)
    with pytest.raises(ValueError, match="GitHub App private key not found"):
        manager.create_jwt()


@pytest.mark.asyncio
@respx.mock
async def test_get_installation_token_fetch_and_cache(test_rsa_private_key_pem: str) -> None:
    settings = Settings(GITHUB_APP_ID="123456")
    manager = GitHubAuthManager(settings)

    route = respx.post("https://api.github.com/app/installations/999/access_tokens").mock(
        return_value=Response(
            201,
            json={
                "token": "ghs_test_token_secret",
                "expires_at": "2026-11-01T15:00:00Z",
                "permissions": {"pull_requests": "write"},
            },
        )
    )

    # 1. First fetch: should make API call
    token1 = await manager.get_installation_token(
        installation_id=999,
        private_key_pem=test_rsa_private_key_pem,
    )
    assert token1 == "ghs_test_token_secret"
    assert route.call_count == 1

    # 2. Second fetch: should be served from cache
    token2 = await manager.get_installation_token(
        installation_id=999,
        private_key_pem=test_rsa_private_key_pem,
    )
    assert token2 == "ghs_test_token_secret"
    assert route.call_count == 1  # No extra HTTP request


@pytest.mark.asyncio
@respx.mock
async def test_get_installation_token_expired_cache(test_rsa_private_key_pem: str) -> None:
    settings = Settings(GITHUB_APP_ID="123456")
    manager = GitHubAuthManager(settings)

    route = respx.post("https://api.github.com/app/installations/999/access_tokens").mock(
        side_effect=[
            Response(201, json={"token": "token_v1", "expires_at": "2026-11-01T14:00:00Z"}),
            Response(201, json={"token": "token_v2", "expires_at": "2026-11-01T15:00:00Z"}),
        ]
    )

    token1 = await manager.get_installation_token(
        installation_id=999,
        private_key_pem=test_rsa_private_key_pem,
    )
    assert token1 == "token_v1"

    # Manually expire the cached token
    manager._tokens_cache[999].expires_at_epoch = time.time() - 10

    token2 = await manager.get_installation_token(
        installation_id=999,
        private_key_pem=test_rsa_private_key_pem,
    )
    assert token2 == "token_v2"
    assert route.call_count == 2
