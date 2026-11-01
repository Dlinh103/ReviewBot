"""GitHub REST API client with automatic token refreshing, pagination, and retries."""

import asyncio
import logging
from typing import Any

import httpx

from reviewbot.config import Settings, get_settings
from reviewbot.github.auth import GitHubAuthManager

logger = logging.getLogger("reviewbot.github.client")


class GitHubAPIError(Exception):
    """Raised when a GitHub API request fails."""

    def __init__(self, status_code: int, message: str, response_body: str = "") -> None:
        super().__init__(f"GitHub API Error {status_code}: {message}")
        self.status_code = status_code
        self.message = message
        self.response_body = response_body


class GitHubClient:
    """Async client interacting with GitHub REST API v3."""

    SUMMARY_MARKER = "<!-- reviewbot:summary -->"

    def __init__(
        self,
        installation_id: int | None = None,
        auth_manager: GitHubAuthManager | None = None,
        settings: Settings | None = None,
        http_client: httpx.AsyncClient | None = None,
        base_url: str = "https://api.github.com",
    ) -> None:
        self.installation_id = installation_id
        self.settings = settings or get_settings()
        self.auth_manager = auth_manager or GitHubAuthManager(self.settings)
        self.base_url = base_url.rstrip("/")

        self._external_client = http_client is not None
        self._client = http_client or httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.settings.LLM_TIMEOUT_SECONDS,
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "reviewbot/0.1.0",
            },
        )

    async def __aenter__(self) -> "GitHubClient":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the underlying HTTP client if created internally."""
        if not self._external_client:
            await self._client.aclose()

    async def _get_auth_header(self) -> dict[str, str]:
        """Obtain authorization header using installation token."""
        if self.installation_id is None:
            return {}
        token = await self.auth_manager.get_installation_token(
            self.installation_id,
            client=self._client,
        )
        return {"Authorization": f"Bearer {token}"}

    async def _request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json_data: Any = None,
        max_retries: int = 3,
    ) -> httpx.Response:
        """Execute HTTP request with authentication and exponential backoff retry."""
        auth_headers = await self._get_auth_header()
        combined_headers = {**auth_headers, **(headers or {})}

        delay = 1.0
        for attempt in range(1, max_retries + 1):
            try:
                response = await self._client.request(
                    method=method,
                    url=path,
                    headers=combined_headers,
                    params=params,
                    json=json_data,
                )

                # Check for rate limit (429 or remaining == 0)
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", int(delay)))
                    logger.warning(
                        "Rate limit hit on %s %s. Waiting %ds (attempt %d/%d)",
                        method, path, retry_after, attempt, max_retries,
                    )
                    if attempt == max_retries:
                        response.raise_for_status()
                    await asyncio.sleep(retry_after)
                    delay *= 2
                    continue

                # Check for server transient errors (5xx)
                if response.status_code >= 500:
                    logger.warning(
                        "GitHub server error %d on %s %s (attempt %d/%d)",
                        response.status_code, method, path, attempt, max_retries,
                    )
                    if attempt == max_retries:
                        response.raise_for_status()
                    await asyncio.sleep(delay)
                    delay *= 2
                    continue

                response.raise_for_status()
                return response

            except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                if attempt == max_retries:
                    err_body = ""
                    status = 500
                    if isinstance(exc, httpx.HTTPStatusError):
                        status = exc.response.status_code
                        err_body = exc.response.text
                    logger.error(
                        "Request failed %s %s after %d retries: %s",
                        method, path, max_retries, exc,
                    )
                    raise GitHubAPIError(status, str(exc), err_body) from exc
                await asyncio.sleep(delay)
                delay *= 2

        raise GitHubAPIError(500, "Unexpected retry loop termination")

    async def get_pull_request(self, repo_full_name: str, pr_number: int) -> dict[str, Any]:
        """Fetch metadata for a pull request."""
        path = f"/repos/{repo_full_name}/pulls/{pr_number}"
        response = await self._request("GET", path)
        return response.json()

    async def get_pr_files(
        self,
        repo_full_name: str,
        pr_number: int,
        per_page: int = 100,
    ) -> list[dict[str, Any]]:
        """Fetch all files changed in a PR with automatic pagination."""
        files: list[dict[str, Any]] = []
        page = 1
        path = f"/repos/{repo_full_name}/pulls/{pr_number}/files"

        while True:
            response = await self._request(
                "GET",
                path,
                params={"per_page": per_page, "page": page},
            )
            page_files: list[dict[str, Any]] = response.json()
            if not page_files:
                break
            files.extend(page_files)
            if len(page_files) < per_page:
                break
            page += 1

        logger.info(
            "Retrieved %d changed files across %d page(s) for %s#%s",
            len(files), page, repo_full_name, pr_number,
        )
        return files

    async def get_file_content(
        self,
        repo_full_name: str,
        file_path: str,
        ref: str,
    ) -> str | None:
        """Fetch raw contents of a file at a specific Git reference."""
        path = f"/repos/{repo_full_name}/contents/{file_path}"
        try:
            response = await self._request(
                "GET",
                path,
                params={"ref": ref},
                headers={"Accept": "application/vnd.github.raw+json"},
            )
            return response.text
        except GitHubAPIError as err:
            if err.status_code == 404:
                logger.debug("File %s not found at ref %s in %s", file_path, ref, repo_full_name)
                return None
            raise

    async def create_review(
        self,
        repo_full_name: str,
        pr_number: int,
        commit_id: str,
        body: str,
        comments: list[dict[str, Any]],
        event: str = "COMMENT",
    ) -> dict[str, Any]:
        """Post a pull request review with inline comments on modified lines.

        Each comment in comments must have:
        - path: str (file relative path)
        - line: int (line number in the new file)
        - body: str (markdown comment)
        """
        path = f"/repos/{repo_full_name}/pulls/{pr_number}/reviews"

        formatted_comments = [
            {
                "path": c["path"],
                "line": c["line"],
                "side": c.get("side", "RIGHT"),
                "body": c["body"],
            }
            for c in comments
        ]

        payload = {
            "commit_id": commit_id,
            "body": body,
            "event": event,
            "comments": formatted_comments,
        }

        response = await self._request("POST", path, json_data=payload)
        logger.info(
            "Created review on %s#%s at %s with %d inline comments",
            repo_full_name, pr_number, commit_id, len(formatted_comments),
        )
        return response.json()

    async def upsert_issue_comment(
        self,
        repo_full_name: str,
        pr_number: int,
        body: str,
        marker: str = SUMMARY_MARKER,
    ) -> dict[str, Any]:
        """Find existing comment containing marker to update, or create a new comment."""
        # 1. Fetch comments on PR (issues API covers PR comments)
        path = f"/repos/{repo_full_name}/issues/{pr_number}/comments"
        response = await self._request("GET", path, params={"per_page": 100})
        comments: list[dict[str, Any]] = response.json()

        existing_comment: dict[str, Any] | None = None
        for comment in comments:
            comment_body = comment.get("body", "")
            if marker in comment_body:
                existing_comment = comment
                break

        full_body = f"{marker}\n{body}" if marker not in body else body

        # 2. Update if existing comment found
        if existing_comment:
            comment_id = existing_comment["id"]
            update_path = f"/repos/{repo_full_name}/issues/comments/{comment_id}"
            update_res = await self._request("PATCH", update_path, json_data={"body": full_body})
            logger.info(
                "Updated existing PR summary comment #%s on %s#%s",
                comment_id, repo_full_name, pr_number,
            )
            return update_res.json()

        # 3. Create new comment
        create_res = await self._request("POST", path, json_data={"body": full_body})
        created_comment = create_res.json()
        logger.info(
            "Created new PR summary comment #%s on %s#%s",
            created_comment.get("id"), repo_full_name, pr_number,
        )
        return created_comment
