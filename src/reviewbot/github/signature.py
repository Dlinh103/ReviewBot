"""GitHub Webhook HMAC SHA-256 signature verification."""

import hashlib
import hmac


def compute_github_signature(payload_bytes: bytes, secret: str) -> str:
    """Compute GitHub-style HMAC SHA-256 signature string."""
    mac = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256)
    return f"sha256={mac.hexdigest()}"


def verify_github_signature(
    payload_bytes: bytes,
    signature_header: str | None,
    secret: str,
) -> bool:
    """Verify GitHub Webhook X-Hub-Signature-256 header.

    Uses hmac.compare_digest to prevent timing attacks.
    """
    if not signature_header or not secret:
        return False

    prefix = "sha256="
    if not signature_header.startswith(prefix):
        return False

    expected_signature = compute_github_signature(payload_bytes, secret)
    return hmac.compare_digest(expected_signature, signature_header)
