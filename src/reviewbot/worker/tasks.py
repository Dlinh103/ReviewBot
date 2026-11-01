"""Celery background tasks definition for PR code review with database persistence."""

import asyncio
import logging
from typing import Any

from reviewbot.config import get_settings
from reviewbot.db.models import ReviewStatus
from reviewbot.db.repositories import ReviewRepository
from reviewbot.db.session import get_db_session
from reviewbot.github.auth import GitHubAuthManager
from reviewbot.github.client import GitHubClient
from reviewbot.llm.anthropic_client import AnthropicClient
from reviewbot.llm.schemas import Finding, PRSummary
from reviewbot.services.review_service import ReviewService
from reviewbot.worker.celery_app import celery_app

logger = logging.getLogger("reviewbot.worker.tasks")


async def run_review_pipeline(payload: dict[str, Any]) -> dict[str, Any]:
    """Async execution wrapper for PR review pipeline with PostgreSQL persistence."""
    settings = get_settings()
    installation_id = payload.get("installation_id")
    repo_full_name = payload["repo_full_name"]
    pr_number = payload["pr_number"]
    head_sha = payload["head_sha"]
    base_sha = payload.get("base_sha", "")
    pr_title = payload.get("pr_title", "")
    pr_body = payload.get("pr_body", "")
    author = payload.get("author", "")
    github_repo_id = payload.get("github_repo_id") or hash(repo_full_name) & 0x7FFFFFFF

    # 1. Database Session & Idempotency Check
    review_id: int | None = None
    pr_id: int | None = None

    with get_db_session() as session:
        repo_layer = ReviewRepository(session)
        repo_obj = repo_layer.get_or_create_repo(
            github_repo_id=github_repo_id,
            full_name=repo_full_name,
            installation_id=installation_id,
        )
        pr_obj = repo_layer.get_or_create_pr(
            repo_id=repo_obj.id,
            number=pr_number,
            title=pr_title,
            author=author,
            head_sha=head_sha,
            base_sha=base_sha,
        )
        pr_id = pr_obj.id

        # Idempotency: skip if already reviewed for this head_sha unless forced
        force_recheck = payload.get("force", False)
        if not force_recheck and repo_layer.is_already_reviewed(
            github_repo_id=github_repo_id,
            pr_number=pr_number,
            head_sha=head_sha,
        ):
            logger.info(
                "PR %s#%s at %s already reviewed. Skipping.",
                repo_full_name, pr_number, head_sha,
            )
            return {
                "status": "skipped",
                "message": "PR commit already reviewed",
                "repo": repo_full_name,
                "pr_number": pr_number,
                "head_sha": head_sha,
            }

        review_obj = repo_layer.create_or_get_review(
            pr_id=pr_obj.id,
            head_sha=head_sha,
            model=settings.LLM_MODEL,
        )
        review_id = review_obj.id
        repo_layer.update_review_status(review_id, ReviewStatus.RUNNING)

    # 2. Run Review Pipeline
    auth_manager = GitHubAuthManager(settings)
    try:
        async with GitHubClient(
            installation_id=installation_id,
            auth_manager=auth_manager,
            settings=settings,
        ) as github_client:
            llm_client = AnthropicClient(settings=settings)
            service = ReviewService(llm_client=llm_client, settings=settings)

            result = await service.review_pull_request(
                github_client=github_client,
                repo_full_name=repo_full_name,
                pr_number=pr_number,
                head_sha=head_sha,
                pr_title=pr_title,
                pr_body=pr_body,
            )

        # 3. Persist review completion and findings in database
        if review_id is not None and pr_id is not None:
            findings_objs = [Finding.model_validate(f) for f in result.get("findings", [])]
            with get_db_session() as session:
                repo_layer = ReviewRepository(session)
                repo_layer.complete_review(
                    review_id=review_id,
                    github_review_id=result.get("github_review_id"),
                    input_tokens=result.get("input_tokens", 0),
                    output_tokens=result.get("output_tokens", 0),
                    cost_usd=result.get("total_cost_usd", 0.0),
                    duration_ms=result.get("duration_ms", 0),
                    findings=findings_objs,
                )
                # Persist summary if present
                if "summary" in result:
                    summary_obj = PRSummary.model_validate(result["summary"])
                    repo_layer.save_pr_summary(
                        pr_id=pr_id,
                        head_sha=head_sha,
                        summary=summary_obj,
                        github_comment_id=result.get("summary_comment_id"),
                    )

        return result

    except Exception as exc:
        if review_id is not None:
            with get_db_session() as session:
                repo_layer = ReviewRepository(session)
                repo_layer.update_review_status(
                    review_id=review_id,
                    status=ReviewStatus.FAILED,
                    error=str(exc),
                )
        raise


@celery_app.task(name="reviewbot.worker.tasks.review_pull_request", bind=True)
def review_pull_request(_self: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """Background task to review a GitHub pull request."""
    repo = payload.get("repo_full_name")
    pr_num = payload.get("pr_number")
    head = payload.get("head_sha")
    logger.info("Executing Celery task review_pull_request for %s#%s (%s)", repo, pr_num, head)

    try:
        result = asyncio.run(run_review_pipeline(payload))
        logger.info("Completed review task for %s#%s: %s", repo, pr_num, result.get("status"))
        return result
    except Exception as exc:
        logger.exception("Failed to review PR %s#%s: %s", repo, pr_num, exc)
        return {
            "status": "failed",
            "repo": repo,
            "pr_number": pr_num,
            "head_sha": head,
            "error": str(exc),
        }


async def run_command_pipeline(payload: dict[str, Any]) -> dict[str, Any]:
    """Async execution wrapper for GitHub PR slash commands (/review, /explain, /suggest-test)."""
    settings = get_settings()
    command = payload["command"]
    repo_full_name = payload["repo_full_name"]
    pr_number = payload["pr_number"]
    installation_id = payload.get("installation_id")
    author = payload.get("author", "developer")

    auth_manager = GitHubAuthManager(settings)
    async with GitHubClient(
        installation_id=installation_id,
        auth_manager=auth_manager,
        settings=settings,
    ) as github_client:
        pr_data = await github_client.get_pull_request(repo_full_name, pr_number)
        head_sha = pr_data.get("head", {}).get("sha", "")

        if command == "/review":
            review_payload = {
                "installation_id": installation_id,
                "repo_full_name": repo_full_name,
                "github_repo_id": pr_data.get("base", {}).get("repo", {}).get("id"),
                "pr_number": pr_number,
                "pr_title": pr_data.get("title", ""),
                "pr_body": pr_data.get("body", ""),
                "head_sha": head_sha,
                "base_sha": pr_data.get("base", {}).get("sha", ""),
                "author": pr_data.get("user", {}).get("login", ""),
                "force": True,
            }
            logger.info(
                "Triggering manual re-review for %s#%s upon /review command",
                repo_full_name,
                pr_number,
            )
            return await run_review_pipeline(review_payload)

        elif command == "/explain":
            llm_client = AnthropicClient(settings=settings)
            prompt = (
                f"Explain the architecture, key changes, and impact of PR #{pr_number} "
                f"'{pr_data.get('title')}' in clear, concise Vietnamese.\n"
                f"PR Description:\n{pr_data.get('body')}"
            )
            resp = await llm_client.generate_json(
                system_prompt=(
                    "You are a principal engineer providing a friendly, "
                    "educational code walkthrough."
                ),
                user_prompt=prompt,
            )
            body = (
                f"> 🤖 **ReviewBot PR Walkthrough & Explanation** (Requested by @{author})\n\n"
                f"{resp.content}\n\n---\n*Triggered via `/explain` command*"
            )
            await github_client.upsert_issue_comment(
                repo_full_name=repo_full_name,
                pr_number=pr_number,
                body=body,
                marker="<!-- reviewbot:command:explain -->",
            )
            return {
                "status": "success",
                "command": "/explain",
                "repo": repo_full_name,
                "pr_number": pr_number,
            }

        elif command == "/suggest-test":
            llm_client = AnthropicClient(settings=settings)
            prompt = (
                f"Generate automated test cases (pytest or unit tests) for PR #{pr_number} "
                f"'{pr_data.get('title')}'. Cover happy path, edge cases, and error handling.\n"
                f"PR Description:\n{pr_data.get('body')}"
            )
            resp = await llm_client.generate_json(
                system_prompt=(
                    "You are a senior QA automation engineer writing clean, "
                    "robust unit tests with assertions."
                ),
                user_prompt=prompt,
            )
            body = (
                f"> 🤖 **ReviewBot Suggested Unit Tests** (Requested by @{author})\n\n"
                f"{resp.content}\n\n---\n*Triggered via `/suggest-test` command*"
            )
            await github_client.upsert_issue_comment(
                repo_full_name=repo_full_name,
                pr_number=pr_number,
                body=body,
                marker="<!-- reviewbot:command:suggest-test -->",
            )
            return {
                "status": "success",
                "command": "/suggest-test",
                "repo": repo_full_name,
                "pr_number": pr_number,
            }

    return {"status": "unrecognized_command", "command": command}


@celery_app.task(name="reviewbot.worker.tasks.handle_pr_command", bind=True)
def handle_pr_command(_self: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """Background task to execute PR comment slash commands."""
    cmd = payload.get("command")
    repo = payload.get("repo_full_name")
    pr_num = payload.get("pr_number")
    logger.info("Executing Celery task handle_pr_command '%s' for %s#%s", cmd, repo, pr_num)

    try:
        result = asyncio.run(run_command_pipeline(payload))
        logger.info(
            "Completed command task '%s' for %s#%s: %s",
            cmd, repo, pr_num, result.get("status"),
        )
        return result
    except Exception as exc:
        logger.exception("Failed to execute command '%s' on %s#%s: %s", cmd, repo, pr_num, exc)
        return {
            "status": "failed",
            "command": cmd,
            "repo": repo,
            "pr_number": pr_num,
            "error": str(exc),
        }
