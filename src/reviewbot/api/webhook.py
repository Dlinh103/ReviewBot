"""GitHub Webhook receiver endpoint."""

import json
import logging
import time
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status

from reviewbot.config import Settings, get_settings
from reviewbot.db.repositories import ReviewRepository
from reviewbot.db.session import create_all_tables, get_db_session
from reviewbot.github.signature import verify_github_signature
from reviewbot.worker.tasks import handle_pr_command, review_pull_request

router = APIRouter(prefix="/webhook", tags=["Webhook"])
logger = logging.getLogger("reviewbot.webhook")

SUPPORTED_ACTIONS = {"opened", "synchronize", "reopened"}


def _persist_delivery(
    delivery_id: str | None,
    event: str,
    action: str | None,
    repo_name: str | None,
    status: str,
    status_code: int,
    duration_ms: int,
    summary: str | None = None,
    error: str | None = None,
) -> None:
    try:
        deliv_id = delivery_id or f"del_{uuid.uuid4().hex[:16]}"
        create_all_tables()
        with get_db_session() as session:
            repo = ReviewRepository(session)
            repo.log_webhook_delivery(
                delivery_id=deliv_id,
                event=event,
                action=action,
                repo_name=repo_name,
                status=status,
                status_code=status_code,
                duration_ms=duration_ms,
                payload_summary=summary,
                error=error,
            )
    except Exception as exc:
        logger.debug("Failed to persist webhook delivery to DB: %s", exc)


@router.post("/github", status_code=status.HTTP_202_ACCEPTED)
async def github_webhook(
    request: Request,
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
    x_github_event: Annotated[str | None, Header(alias="X-GitHub-Event")] = None,
    x_hub_signature_256: Annotated[str | None, Header(alias="X-Hub-Signature-256")] = None,
    x_github_delivery: Annotated[str | None, Header(alias="X-GitHub-Delivery")] = None,
) -> dict[str, Any]:
    """Receive and process GitHub webhook events."""
    start_time = time.perf_counter()
    body_bytes = await request.body()

    # 1. Verify HMAC SHA-256 Signature
    if settings.GITHUB_WEBHOOK_SECRET:
        if not verify_github_signature(
            body_bytes,
            x_hub_signature_256,
            settings.GITHUB_WEBHOOK_SECRET,
        ):
            logger.warning("Rejected webhook: invalid signature, delivery=%s", x_github_delivery)
            _persist_delivery(
                x_github_delivery,
                x_github_event or "unknown",
                None,
                None,
                "failed",
                status.HTTP_401_UNAUTHORIZED,
                int((time.perf_counter() - start_time) * 1000),
                error="Invalid X-Hub-Signature-256",
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid X-Hub-Signature-256",
            )

    # 2. Handle ping event
    if x_github_event == "ping":
        response.status_code = status.HTTP_200_OK
        logger.info("Received ping event from GitHub (delivery=%s)", x_github_delivery)
        _persist_delivery(
            x_github_delivery,
            "ping",
            None,
            None,
            "accepted",
            status.HTTP_200_OK,
            int((time.perf_counter() - start_time) * 1000),
            summary="GitHub webhook ping handshake",
        )
        return {"status": "ok", "message": "Pong"}

    # 3. Only handle pull_request and issue_comment events
    if x_github_event not in ("pull_request", "issue_comment"):
        logger.info(
            "Ignored unsupported event '%s' (delivery=%s)",
            x_github_event,
            x_github_delivery,
        )
        _persist_delivery(
            x_github_delivery,
            x_github_event or "unknown",
            None,
            None,
            "ignored",
            status.HTTP_200_OK,
            int((time.perf_counter() - start_time) * 1000),
            summary=f"Unsupported event type: {x_github_event}",
        )
        return {
            "status": "ignored",
            "reason": f"Unsupported event type: {x_github_event}",
        }

    # 4. Parse payload
    try:
        payload = json.loads(body_bytes.decode("utf-8"))
    except Exception as exc:
        logger.error("Failed to parse webhook JSON body: %s", exc)
        _persist_delivery(
            x_github_delivery,
            x_github_event or "unknown",
            None,
            None,
            "failed",
            status.HTTP_400_BAD_REQUEST,
            int((time.perf_counter() - start_time) * 1000),
            error="Invalid JSON payload",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        ) from exc

    # 5. Handle issue_comment events (slash commands: /review, /explain, /suggest-test)
    if x_github_event == "issue_comment":
        action = payload.get("action")
        if action != "created":
            logger.info("Ignored issue_comment action '%s'", action)
            _persist_delivery(
                x_github_delivery,
                "issue_comment",
                action,
                payload.get("repository", {}).get("full_name"),
                "ignored",
                status.HTTP_200_OK,
                int((time.perf_counter() - start_time) * 1000),
                summary=f"Unsupported issue_comment action: {action}",
            )
            return {"status": "ignored", "reason": f"Unsupported issue_comment action: {action}"}

        issue = payload.get("issue", {})
        if "pull_request" not in issue:
            _persist_delivery(
                x_github_delivery,
                "issue_comment",
                action,
                payload.get("repository", {}).get("full_name"),
                "ignored",
                status.HTTP_200_OK,
                int((time.perf_counter() - start_time) * 1000),
                summary="Comment is not on a pull request",
            )
            return {"status": "ignored", "reason": "Comment is not on a pull request"}

        comment = payload.get("comment", {})
        comment_user = comment.get("user", {})
        if (
            comment_user.get("type", "").lower() == "bot"
            or comment_user.get("login", "").endswith("[bot]")
        ):
            return {"status": "ignored", "reason": "Comment is by a bot"}

        body_text = comment.get("body", "").strip()
        matched_cmd = None
        for cmd in ("/review", "/explain", "/suggest-test"):
            if body_text.startswith(cmd) or f"\n{cmd}" in body_text:
                matched_cmd = cmd
                break

        if not matched_cmd:
            return {"status": "ignored", "reason": "No supported slash command found"}

        repo = payload.get("repository", {})
        repo_full_name = repo.get("full_name")
        pr_number = issue.get("number")
        installation_id = payload.get("installation", {}).get("id")

        cmd_payload = {
            "command": matched_cmd,
            "repo_full_name": repo_full_name,
            "pr_number": pr_number,
            "installation_id": installation_id,
            "author": comment_user.get("login", "developer"),
            "comment_body": body_text,
        }

        handle_pr_command.delay(cmd_payload)
        logger.info(
            "Dispatched slash command '%s' for PR %s#%s",
            matched_cmd, repo_full_name, pr_number,
        )
        _persist_delivery(
            x_github_delivery,
            "issue_comment",
            action,
            repo_full_name,
            "enqueued",
            status.HTTP_202_ACCEPTED,
            int((time.perf_counter() - start_time) * 1000),
            summary=f"Command {matched_cmd} enqueued for PR #{pr_number}",
        )
        return {
            "status": "enqueued",
            "command": matched_cmd,
            "repo": repo_full_name,
            "pr_number": pr_number,
        }

    # 6. Handle pull_request events
    action = payload.get("action")
    if action not in SUPPORTED_ACTIONS:
        logger.info("Ignored pull_request action '%s'", action)
        _persist_delivery(
            x_github_delivery,
            "pull_request",
            action,
            payload.get("repository", {}).get("full_name"),
            "ignored",
            status.HTTP_200_OK,
            int((time.perf_counter() - start_time) * 1000),
            summary=f"Unsupported action: {action}",
        )
        return {
            "status": "ignored",
            "reason": f"Unsupported action: {action}",
        }

    pr = payload.get("pull_request", {})
    repo = payload.get("repository", {})
    sender = payload.get("sender", {})
    user = pr.get("user", {})

    # 5. Check if draft PR
    is_draft = pr.get("draft", False)
    if is_draft and not settings.REVIEW_DRAFT_PRS:
        logger.info("Ignored draft PR #%s in %s", pr.get("number"), repo.get("full_name"))
        _persist_delivery(
            x_github_delivery,
            "pull_request",
            action,
            repo.get("full_name"),
            "ignored",
            status.HTTP_200_OK,
            int((time.perf_counter() - start_time) * 1000),
            summary=f"PR #{pr.get('number')} is in draft state",
        )
        return {
            "status": "ignored",
            "reason": "PR is in draft state",
        }

    # 6. Check if PR was created by a bot
    author_login = user.get("login", "")
    author_type = user.get("type", "")
    sender_type = sender.get("type", "")
    if (
        author_type.lower() == "bot"
        or author_login.endswith("[bot]")
        or sender_type.lower() == "bot"
    ):
        logger.info("Ignored PR #%s by bot '%s'", pr.get("number"), author_login)
        _persist_delivery(
            x_github_delivery,
            "pull_request",
            action,
            repo.get("full_name"),
            "ignored",
            status.HTTP_200_OK,
            int((time.perf_counter() - start_time) * 1000),
            summary=f"PR #{pr.get('number')} author is a bot ({author_login})",
        )
        return {
            "status": "ignored",
            "reason": "PR author is a bot",
        }

    # 7. Extract minimal review task payload
    installation = payload.get("installation", {})
    installation_id = installation.get("id") if installation else None
    repo_full_name = repo.get("full_name")
    pr_number = pr.get("number")
    head_sha = pr.get("head", {}).get("sha")
    base_sha = pr.get("base", {}).get("sha")

    if not repo_full_name or not pr_number or not head_sha:
        logger.error("Missing mandatory fields in PR payload (repo=%s, pr=%s, sha=%s)",
                     repo_full_name, pr_number, head_sha)
        _persist_delivery(
            x_github_delivery,
            "pull_request",
            action,
            repo_full_name,
            "failed",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            int((time.perf_counter() - start_time) * 1000),
            error="Missing mandatory fields in PR payload",
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Missing required pull request fields",
        )

    task_payload = {
        "installation_id": installation_id,
        "repo_full_name": repo_full_name,
        "pr_number": pr_number,
        "head_sha": head_sha,
        "base_sha": base_sha,
        "pr_title": pr.get("title", ""),
        "pr_body": pr.get("body", "") or "",
        "author": author_login,
        "action": action,
    }

    # 8. Enqueue Celery task asynchronously
    review_pull_request.delay(task_payload)
    logger.info(
        "Enqueued review for %s#%s (head: %s, action: %s)",
        repo_full_name,
        pr_number,
        head_sha,
        action,
    )
    _persist_delivery(
        x_github_delivery,
        "pull_request",
        action,
        repo_full_name,
        "accepted",
        status.HTTP_202_ACCEPTED,
        int((time.perf_counter() - start_time) * 1000),
        summary=f"PR #{pr_number} ({pr.get('title', '')}) review task queued",
    )

    return {
        "status": "accepted",
        "message": "Pull request review queued",
        "repo": repo_full_name,
        "pr": pr_number,
        "head_sha": head_sha,
    }
