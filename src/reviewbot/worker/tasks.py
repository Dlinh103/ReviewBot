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

        # Idempotency: skip if already reviewed for this head_sha
        if repo_layer.is_already_reviewed(
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
