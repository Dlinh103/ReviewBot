"""Unit tests for GitHub webhook signature verification."""

from reviewbot.github.signature import compute_github_signature, verify_github_signature

SECRET = "super-secret-key-12345"
PAYLOAD = b'{"action": "opened", "number": 1}'


def test_compute_signature() -> None:
    sig = compute_github_signature(PAYLOAD, SECRET)
    assert sig.startswith("sha256=")
    assert len(sig) == 7 + 64


def test_verify_signature_valid() -> None:
    sig = compute_github_signature(PAYLOAD, SECRET)
    assert verify_github_signature(PAYLOAD, sig, SECRET) is True


def test_verify_signature_tampered_payload() -> None:
    sig = compute_github_signature(PAYLOAD, SECRET)
    tampered = b'{"action": "opened", "number": 2}'
    assert verify_github_signature(tampered, sig, SECRET) is False


def test_verify_signature_wrong_secret() -> None:
    sig = compute_github_signature(PAYLOAD, SECRET)
    assert verify_github_signature(PAYLOAD, sig, "wrong-secret") is False


def test_verify_signature_missing_prefix() -> None:
    raw_hash = compute_github_signature(PAYLOAD, SECRET).replace("sha256=", "")
    assert verify_github_signature(PAYLOAD, raw_hash, SECRET) is False


def test_verify_signature_empty_inputs() -> None:
    sig = compute_github_signature(PAYLOAD, SECRET)
    assert verify_github_signature(PAYLOAD, None, SECRET) is False
    assert verify_github_signature(PAYLOAD, "", SECRET) is False
    assert verify_github_signature(PAYLOAD, sig, "") is False
