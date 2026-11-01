"""Detect and redact secrets, credentials, and API keys prior to LLM processing."""

import re

# Compiled secret detection patterns
SECRET_PATTERNS: list[tuple[re.Pattern, str]] = [
    # 1. Private keys (PEM blocks)
    (
        re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----[\s\S]*?-----END [A-Z ]+ PRIVATE KEY-----"),
        "[REDACTED_PRIVATE_KEY]",
    ),
    # 2. AWS Access Key ID
    (
        re.compile(r"\b(AKIA|ABIA|ACCA|ASIA)[0-9A-Z]{16}\b"),
        "[REDACTED_AWS_KEY_ID]",
    ),
    # 3. AWS Secret Access Key assignment
    (
        re.compile(
            r"""(?i)(aws_secret_access_key|aws_secret_key)\s*[:=]\s*['"][A-Za-z0-9/\+=]{40}['"]"""
        ),
        r"\1=[REDACTED_AWS_SECRET]",
    ),
    # 4. GitHub Tokens
    (
        re.compile(r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,255}\b"),
        "[REDACTED_GITHUB_TOKEN]",
    ),
    (
        re.compile(r"\bgithub_pat_[A-Za-z0-9_]{82}\b"),
        "[REDACTED_GITHUB_PAT]",
    ),
    # 5. JWT Tokens (header.payload.signature)
    (
        re.compile(r"\beyJ[A-Za-z0-9-_=]+\.eyJ[A-Za-z0-9-_=]+\.[A-Za-z0-9-_.+/=]+\b"),
        "[REDACTED_JWT_TOKEN]",
    ),
    # 6. Slack Tokens
    (
        re.compile(r"\bxox[baprs]-[0-9A-Za-z]{10,48}\b"),
        "[REDACTED_SLACK_TOKEN]",
    ),
    # 7. Stripe API Keys
    (
        re.compile(r"\b(?:sk|pk)_(?:test|live)_[0-9a-zA-Z]{24,99}\b"),
        "[REDACTED_STRIPE_KEY]",
    ),
    # 8. Generic password / secret / token assignments in code/config
    # Avoid replacing already-redacted tokens (those starting with [REDACTED_)
    (
        re.compile(
            r"""(?i)\b([a-z0-9_-]*(?:api_key|apikey|secret|password|passwd|auth_token|client_secret)[a-z0-9_-]*)\s*[:=]\s*['"](?!\s*\[REDACTED_)([^'"\s]{6,})['"]"""
        ),
        r"\1=[REDACTED_CREDENTIAL]",
    ),
]


def scrub_secrets(text: str) -> tuple[str, int]:
    """Redact sensitive credentials from text.

    Returns:
        (scrubbed_text, count_of_redactions)
    """
    if not text:
        return text, 0

    scrubbed = text
    total_redactions = 0

    for pattern, replacement in SECRET_PATTERNS:
        matches = len(pattern.findall(scrubbed))
        if matches > 0:
            total_redactions += matches
            scrubbed = pattern.sub(replacement, scrubbed)

    return scrubbed, total_redactions
