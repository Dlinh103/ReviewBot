"""Unit tests for GitHub webhook endpoint."""

import json
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import httpx
import pytest

from reviewbot.config import Settings, get_settings
from reviewbot.github.signature import compute_github_signature
from reviewbot.main import app

TEST_SECRET = "webhook-test-secret"


@pytest.fixture(autouse=True)
def mock_celery_task() -> Generator[MagicMock, None, None]:
    """Globally mock Celery delay in all webhook tests to avoid connecting to Redis."""
    with (
        patch("reviewbot.api.webhook.review_pull_request.delay") as mock_delay,
        patch("reviewbot.api.webhook.handle_pr_command.delay"),
    ):
        yield mock_delay


@pytest.fixture(autouse=True)
def override_settings() -> Generator[Settings, None, None]:
    """Fixture providing overridden settings with test webhook secret."""
    test_settings = Settings(
        GITHUB_WEBHOOK_SECRET=TEST_SECRET,
        REVIEW_DRAFT_PRS=False,
    )
    app.dependency_overrides[get_settings] = lambda: test_settings
    yield test_settings
    app.dependency_overrides.clear()


def make_pr_payload(
    action: str = "opened",
    is_draft: bool = False,
    author_login: str = "octocat",
    author_type: str = "User",
    sender_type: str = "User",
) -> dict:
    """Helper to build realistic GitHub pull_request webhook payload."""
    return {
        "action": action,
        "installation": {"id": 123456},
        "repository": {
            "id": 987654,
            "full_name": "octocat/Hello-World",
            "name": "Hello-World",
        },
        "pull_request": {
            "number": 42,
            "title": "Add exciting new feature",
            "body": "This PR implements feature X.",
            "draft": is_draft,
            "user": {
                "login": author_login,
                "type": author_type,
            },
            "head": {
                "sha": "6dcb09b5b57875f334f61aebed695e2e4193db5e",
                "ref": "feature-x",
            },
            "base": {
                "sha": "7d9b65e2361b17b165bf25916c0ddb3227a69bc9",
                "ref": "main",
            },
        },
        "sender": {
            "login": author_login,
            "type": sender_type,
        },
    }


@pytest.mark.asyncio
async def test_webhook_missing_signature() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        payload = make_pr_payload()
        response = await client.post(
            "/webhook/github",
            headers={"X-GitHub-Event": "pull_request"},
            json=payload,
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid X-Hub-Signature-256"


@pytest.mark.asyncio
async def test_webhook_invalid_signature() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        payload = make_pr_payload()
        response = await client.post(
            "/webhook/github",
            headers={
                "X-GitHub-Event": "pull_request",
                "X-Hub-Signature-256": "sha256=" + "0" * 64,
            },
            json=payload,
        )
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_webhook_ping_event() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        body = json.dumps({"zen": "Keep it logically awesome."}).encode("utf-8")
        sig = compute_github_signature(body, TEST_SECRET)
        response = await client.post(
            "/webhook/github",
            headers={
                "X-GitHub-Event": "ping",
                "X-Hub-Signature-256": sig,
                "Content-Type": "application/json",
            },
            content=body,
        )
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "message": "Pong"}


@pytest.mark.asyncio
async def test_webhook_ignored_unsupported_event() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        body = json.dumps({"ref": "refs/heads/main"}).encode("utf-8")
        sig = compute_github_signature(body, TEST_SECRET)
        response = await client.post(
            "/webhook/github",
            headers={
                "X-GitHub-Event": "push",
                "X-Hub-Signature-256": sig,
                "Content-Type": "application/json",
            },
            content=body,
        )
        assert response.status_code == 202
        assert response.json()["status"] == "ignored"
        assert "Unsupported event type" in response.json()["reason"]


@pytest.mark.asyncio
async def test_webhook_ignored_unsupported_action() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        payload = make_pr_payload(action="closed")
        body = json.dumps(payload).encode("utf-8")
        sig = compute_github_signature(body, TEST_SECRET)
        response = await client.post(
            "/webhook/github",
            headers={
                "X-GitHub-Event": "pull_request",
                "X-Hub-Signature-256": sig,
                "Content-Type": "application/json",
            },
            content=body,
        )
        assert response.status_code == 202
        assert response.json()["status"] == "ignored"
        assert response.json()["reason"] == "Unsupported action: closed"


@pytest.mark.asyncio
async def test_webhook_ignored_draft_pr() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        payload = make_pr_payload(action="opened", is_draft=True)
        body = json.dumps(payload).encode("utf-8")
        sig = compute_github_signature(body, TEST_SECRET)
        response = await client.post(
            "/webhook/github",
            headers={
                "X-GitHub-Event": "pull_request",
                "X-Hub-Signature-256": sig,
                "Content-Type": "application/json",
            },
            content=body,
        )
        assert response.status_code == 202
        assert response.json()["status"] == "ignored"
        assert response.json()["reason"] == "PR is in draft state"


@pytest.mark.asyncio
async def test_webhook_ignored_bot_author() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        payload = make_pr_payload(
            action="opened",
            author_login="dependabot[bot]",
            author_type="Bot",
        )
        body = json.dumps(payload).encode("utf-8")
        sig = compute_github_signature(body, TEST_SECRET)
        response = await client.post(
            "/webhook/github",
            headers={
                "X-GitHub-Event": "pull_request",
                "X-Hub-Signature-256": sig,
                "Content-Type": "application/json",
            },
            content=body,
        )
        assert response.status_code == 202
        assert response.json()["status"] == "ignored"
        assert response.json()["reason"] == "PR author is a bot"


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["opened", "synchronize", "reopened"])
async def test_webhook_accepted_valid_pr(
    action: str,
    mock_celery_task: MagicMock,
) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        payload = make_pr_payload(action=action)
        body = json.dumps(payload).encode("utf-8")
        sig = compute_github_signature(body, TEST_SECRET)
        response = await client.post(
            "/webhook/github",
            headers={
                "X-GitHub-Event": "pull_request",
                "X-Hub-Signature-256": sig,
                "Content-Type": "application/json",
            },
            content=body,
        )
        assert response.status_code == 202
        res_data = response.json()
        assert res_data["status"] == "accepted"
        assert res_data["repo"] == "octocat/Hello-World"
        assert res_data["pr"] == 42
        assert res_data["head_sha"] == "6dcb09b5b57875f334f61aebed695e2e4193db5e"

        # Verify Celery delay was called with required fields
        mock_celery_task.assert_called_once()
        task_call_args = mock_celery_task.call_args[0][0]
        assert task_call_args["installation_id"] == 123456
        assert task_call_args["repo_full_name"] == "octocat/Hello-World"
        assert task_call_args["pr_number"] == 42
        assert task_call_args["head_sha"] == "6dcb09b5b57875f334f61aebed695e2e4193db5e"
        assert task_call_args["action"] == action
        assert task_call_args["author"] == "octocat"


@pytest.mark.asyncio
@pytest.mark.parametrize("cmd", ["/review", "/explain", "/suggest-test"])
async def test_webhook_issue_comment_commands(cmd: str) -> None:
    transport = httpx.ASGITransport(app=app)
    with patch("reviewbot.api.webhook.handle_pr_command.delay") as mock_cmd:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "action": "created",
                "installation": {"id": 999},
                "repository": {"full_name": "octocat/Hello-World"},
                "issue": {"number": 101, "pull_request": {"url": "https://api.github.com/..."}},
                "comment": {
                    "body": f"{cmd} please analyze this PR",
                    "user": {"login": "alice", "type": "User"},
                },
            }
            body = json.dumps(payload).encode("utf-8")
            sig = compute_github_signature(body, TEST_SECRET)
            response = await client.post(
                "/webhook/github",
                headers={
                    "X-GitHub-Event": "issue_comment",
                    "X-Hub-Signature-256": sig,
                    "Content-Type": "application/json",
                },
                content=body,
            )
            assert response.status_code == 202
            data = response.json()
            assert data["status"] == "enqueued"
            assert data["command"] == cmd
            mock_cmd.assert_called_once()
            args = mock_cmd.call_args[0][0]
            assert args["command"] == cmd
            assert args["pr_number"] == 101
            assert args["repo_full_name"] == "octocat/Hello-World"


@pytest.mark.asyncio
async def test_webhook_issue_comment_non_pr_ignored() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "action": "created",
            "repository": {"full_name": "octocat/Hello-World"},
            "issue": {"number": 101},  # No pull_request key -> regular issue
            "comment": {
                "body": "/review",
                "user": {"login": "alice", "type": "User"},
            },
        }
        body = json.dumps(payload).encode("utf-8")
        sig = compute_github_signature(body, TEST_SECRET)
        response = await client.post(
            "/webhook/github",
            headers={
                "X-GitHub-Event": "issue_comment",
                "X-Hub-Signature-256": sig,
                "Content-Type": "application/json",
            },
            content=body,
        )
        assert response.status_code == 202
        assert response.json()["status"] == "ignored"
