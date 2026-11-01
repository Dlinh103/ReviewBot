"""Unit tests for SecretsScrubber."""

from pathlib import Path

from reviewbot.core.secrets_scrubber import scrub_secrets

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_scrub_aws_keys() -> None:
    text = (
        "AWS_KEY = 'AKIAIOSFODNN7EXAMPLE'\n"
        "aws_secret_access_key='wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'"
    )
    scrubbed, count = scrub_secrets(text)
    assert count >= 2
    assert "AKIAIOSFODNN7EXAMPLE" not in scrubbed
    assert "[REDACTED_AWS_KEY_ID]" in scrubbed
    assert "[REDACTED_AWS_SECRET]" in scrubbed


def test_scrub_github_tokens() -> None:
    text = "gh_pat = 'ghp_0123456789abcdefghijklmnopqrstuvwxyz'"
    scrubbed, count = scrub_secrets(text)
    assert count >= 1
    assert "ghp_0123456789abcdefghijklmnopqrstuvwxyz" not in scrubbed
    assert "[REDACTED_GITHUB_TOKEN]" in scrubbed


def test_scrub_private_key_pem() -> None:
    text = """-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA0Y1+exampleFakePrivateKeyContent...
-----END RSA PRIVATE KEY-----"""
    scrubbed, count = scrub_secrets(text)
    assert count >= 1
    assert "exampleFakePrivateKeyContent" not in scrubbed
    assert "[REDACTED_PRIVATE_KEY]" in scrubbed


def test_scrub_stripe_key() -> None:
    text = "stripe.api_key = 'sk_live_51Abc1234567890abcdef12345678'"
    scrubbed, count = scrub_secrets(text)
    assert count >= 1
    assert "sk_live_51Abc1234567890abcdef12345678" not in scrubbed
    assert "[REDACTED_STRIPE_KEY]" in scrubbed


def test_scrub_password_assignment() -> None:
    text = "db_password = 'MySuperSecretPassword123!'"
    scrubbed, count = scrub_secrets(text)
    assert count >= 1
    assert "MySuperSecretPassword123!" not in scrubbed
    assert "[REDACTED_CREDENTIAL]" in scrubbed


def test_scrub_clean_code_unchanged() -> None:
    clean_code = """def add(a: int, b: int) -> int:
    return a + b
"""
    scrubbed, count = scrub_secrets(clean_code)
    assert count == 0
    assert scrubbed == clean_code


def test_scrub_fixtures_secrets() -> None:
    diff_text = (FIXTURES_DIR / "secrets.diff").read_text(encoding="utf-8")
    scrubbed, count = scrub_secrets(diff_text)
    assert count >= 4
    assert "AKIAIOSFODNN7EXAMPLE" not in scrubbed
    assert "ghp_1234567890abcdefghijklmnopqrstuvwxyz" not in scrubbed
    assert "super_secret_master_password_99" not in scrubbed
