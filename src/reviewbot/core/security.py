"""Security utilities for user authentication, password hashing, and JWT tokens."""

import hashlib
import hmac
import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from reviewbot.config import get_settings

logger = logging.getLogger("reviewbot.core.security")

# Hash configuration (NIST SP 800-132 recommendation for PBKDF2-HMAC-SHA256)
PBKDF2_ITERATIONS = 100_000
SALT_SIZE = 16
HASH_ALGORITHM = "sha256"
JWT_ALGORITHM = "HS256"
DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days


def hash_password(plain_password: str) -> str:
    """Hash a plain text password using PBKDF2-HMAC-SHA256 with random salt.

    Format: pbkdf2_sha256${iterations}${salt_hex}${hash_hex}
    """
    salt = os.urandom(SALT_SIZE)
    derived = hashlib.pbkdf2_hmac(
        HASH_ALGORITHM,
        plain_password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${derived.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain text password against a stored PBKDF2 hash using constant-time comparison."""
    if not hashed_password or not plain_password:
        return False

    parts = hashed_password.split("$")
    if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
        logger.warning("Unrecognized password hash format.")
        return False

    try:
        iterations = int(parts[1])
        salt = bytes.fromhex(parts[2])
        expected_hash = bytes.fromhex(parts[3])
    except (ValueError, IndexError):
        return False

    computed_hash = hashlib.pbkdf2_hmac(
        HASH_ALGORITHM,
        plain_password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(computed_hash, expected_hash)


def get_jwt_secret_key() -> str:
    """Get secret key used for signing JWT tokens.

    Ensures at least 256 bits (32 bytes) length to comply with RFC 7518.
    """
    settings = get_settings()
    secret = getattr(settings, "JWT_SECRET_KEY", None) or getattr(
        settings, "GITHUB_WEBHOOK_SECRET", None
    )
    if not secret:
        secret = "reviewbot-vku-se-secure-jwt-signing-secret-key-2026"

    # If the configured secret is shorter than 32 bytes, derive a 256-bit SHA256 key
    raw_secret = str(secret)
    if len(raw_secret.encode("utf-8")) < 32:
        return hashlib.sha256(raw_secret.encode("utf-8")).hexdigest()
    return raw_secret


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT access token."""
    to_encode = data.copy()
    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update(
        {
            "exp": expire,
            "iat": now,
            "iss": "reviewbot-api",
        }
    )

    secret_key = get_jwt_secret_key()
    return jwt.encode(to_encode, secret_key, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT access token.

    Returns the payload dictionary or None if invalid or expired.
    """
    secret_key = get_jwt_secret_key()
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            secret_key,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "iat", "sub"]},
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.debug("JWT token has expired.")
        return None
    except jwt.PyJWTError as exc:
        logger.debug("Invalid JWT token: %s", exc)
        return None
