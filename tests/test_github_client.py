"""Unit tests for GitHubClient using respx for HTTP mocking."""

from unittest.mock import AsyncMock, patch

import pytest
import respx
from httpx import Response

from reviewbot.config import Settings
from reviewbot.github.auth import GitHubAuthManager
from reviewbot.github.client import GitHubAPIError, GitHubClient


@pytest.fixture
def mock_auth_manager() -> GitHubAuthManager:
    """Mock auth manager that returns static installation token."""
    manager = GitHubAuthManager(Settings(GITHUB_APP_ID="123456"))
    manager.get_installation_token = AsyncMock(return_value="mock_install_token")  # type: ignore[method-assign]
    return manager


@pytest.mark.asyncio
@respx.mock
async def test_get_pull_request(mock_auth_manager: GitHubAuthManager) -> None:
    respx.get("https://api.github.com/repos/owner/repo/pulls/10").mock(
        return_value=Response(
            200,
            json={
                "id": 100,
                "number": 10,
                "title": "Fix memory leak",
                "head": {"sha": "head123"},
                "base": {"sha": "base456"},
            },
        )
    )

    async with GitHubClient(installation_id=1, auth_manager=mock_auth_manager) as client:
        pr = await client.get_pull_request("owner/repo", 10)
        assert pr["number"] == 10
        assert pr["title"] == "Fix memory leak"


@pytest.mark.asyncio
@respx.mock
async def test_get_pr_files_pagination(mock_auth_manager: GitHubAuthManager) -> None:
    # Page 1 returns 2 files (per_page=2)
    respx.get("https://api.github.com/repos/owner/repo/pulls/10/files?per_page=2&page=1").mock(
        return_value=Response(
            200,
            json=[
                {"filename": "app/main.py", "status": "modified"},
                {"filename": "app/utils.py", "status": "added"},
            ],
        )
    )
    # Page 2 returns 1 file (less than per_page=2 -> ends pagination)
    respx.get("https://api.github.com/repos/owner/repo/pulls/10/files?per_page=2&page=2").mock(
        return_value=Response(
            200,
            json=[
                {"filename": "tests/test_main.py", "status": "modified"},
            ],
        )
    )

    async with GitHubClient(installation_id=1, auth_manager=mock_auth_manager) as client:
        files = await client.get_pr_files("owner/repo", 10, per_page=2)
        assert len(files) == 3
        filenames = [f["filename"] for f in files]
        assert filenames == ["app/main.py", "app/utils.py", "tests/test_main.py"]


@pytest.mark.asyncio
@respx.mock
async def test_get_file_content_success_and_not_found(
    mock_auth_manager: GitHubAuthManager,
) -> None:
    respx.get("https://api.github.com/repos/owner/repo/contents/main.py?ref=main").mock(
        return_value=Response(200, text="print('Hello world!')")
    )
    respx.get("https://api.github.com/repos/owner/repo/contents/missing.py?ref=main").mock(
        return_value=Response(404, json={"message": "Not Found"})
    )

    async with GitHubClient(installation_id=1, auth_manager=mock_auth_manager) as client:
        content = await client.get_file_content("owner/repo", "main.py", "main")
        assert content == "print('Hello world!')"

        missing = await client.get_file_content("owner/repo", "missing.py", "main")
        assert missing is None


@pytest.mark.asyncio
@respx.mock
async def test_create_review(mock_auth_manager: GitHubAuthManager) -> None:
    route = respx.post("https://api.github.com/repos/owner/repo/pulls/10/reviews").mock(
        return_value=Response(
            200,
            json={"id": 555, "state": "COMMENTED"},
        )
    )

    inline_comments = [
        {
            "path": "app/main.py",
            "line": 42,
            "body": "Potential null pointer dereference here.",
        }
    ]

    async with GitHubClient(installation_id=1, auth_manager=mock_auth_manager) as client:
        review = await client.create_review(
            repo_full_name="owner/repo",
            pr_number=10,
            commit_id="sha999",
            body="Review summary: Found 1 issue.",
            comments=inline_comments,
        )
        assert review["id"] == 555
        assert route.call_count == 1

        request_body = route.calls.last.request.read().decode("utf-8")
        assert "sha999" in request_body
        assert "RIGHT" in request_body
        assert "Potential null pointer dereference" in request_body


@pytest.mark.asyncio
@respx.mock
async def test_upsert_issue_comment_create_new(mock_auth_manager: GitHubAuthManager) -> None:
    # 1. Existing comments list has no marker
    respx.get("https://api.github.com/repos/owner/repo/issues/10/comments?per_page=100").mock(
        return_value=Response(
            200,
            json=[
                {"id": 1, "body": "Great PR!"},
                {"id": 2, "body": "Please add tests."},
            ],
        )
    )
    # 2. POST create endpoint
    post_route = respx.post("https://api.github.com/repos/owner/repo/issues/10/comments").mock(
        return_value=Response(
            201,
            json={"id": 3, "body": "<!-- reviewbot:summary -->\n## PR Summary"},
        )
    )

    async with GitHubClient(installation_id=1, auth_manager=mock_auth_manager) as client:
        comment = await client.upsert_issue_comment(
            repo_full_name="owner/repo",
            pr_number=10,
            body="## PR Summary",
        )
        assert comment["id"] == 3
        assert post_route.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_upsert_issue_comment_update_existing(
    mock_auth_manager: GitHubAuthManager,
) -> None:
    # 1. Existing comments list contains marker
    respx.get("https://api.github.com/repos/owner/repo/issues/10/comments?per_page=100").mock(
        return_value=Response(
            200,
            json=[
                {"id": 1, "body": "Old comment"},
                {"id": 88, "body": "<!-- reviewbot:summary -->\nOld summary content"},
            ],
        )
    )
    # 2. PATCH update endpoint
    patch_route = respx.patch("https://api.github.com/repos/owner/repo/issues/comments/88").mock(
        return_value=Response(
            200,
            json={"id": 88, "body": "<!-- reviewbot:summary -->\nUpdated summary"},
        )
    )

    async with GitHubClient(installation_id=1, auth_manager=mock_auth_manager) as client:
        comment = await client.upsert_issue_comment(
            repo_full_name="owner/repo",
            pr_number=10,
            body="Updated summary",
        )
        assert comment["id"] == 88
        assert patch_route.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_retry_on_server_error(mock_auth_manager: GitHubAuthManager) -> None:
    # First 2 calls return 503, third succeeds
    route = respx.get("https://api.github.com/repos/owner/repo/pulls/10").mock(
        side_effect=[
            Response(503, text="Service Unavailable"),
            Response(502, text="Bad Gateway"),
            Response(200, json={"number": 10, "state": "open"}),
        ]
    )

    with patch("asyncio.sleep", AsyncMock(return_value=None)):
        async with GitHubClient(installation_id=1, auth_manager=mock_auth_manager) as client:
            pr = await client.get_pull_request("owner/repo", 10)
            assert pr["number"] == 10
            assert route.call_count == 3


@pytest.mark.asyncio
@respx.mock
async def test_retry_exhausted_raises_error(mock_auth_manager: GitHubAuthManager) -> None:
    respx.get("https://api.github.com/repos/owner/repo/pulls/10").mock(
        return_value=Response(500, text="Internal Server Error")
    )

    with patch("asyncio.sleep", AsyncMock(return_value=None)):
        async with GitHubClient(installation_id=1, auth_manager=mock_auth_manager) as client:
            with pytest.raises(GitHubAPIError) as exc_info:
                await client.get_pull_request("owner/repo", 10)
            assert exc_info.value.status_code == 500
