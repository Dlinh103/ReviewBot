"""Database access repositories for ReviewBot entities."""

import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from reviewbot.db.models import (
    Category,
    Feedback,
    FindingModel,
    PRSummaryModel,
    PullRequest,
    Reaction,
    Repository,
    Review,
    ReviewStatus,
    Severity,
    SystemRuleConfig,
    WebhookDelivery,
)
from reviewbot.llm.schemas import Finding, PRSummary

logger = logging.getLogger("reviewbot.db.repositories")


class ReviewRepository:
    """Repository managing repositories, PRs, reviews, findings, and summaries."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_or_create_repo(
        self,
        github_repo_id: int,
        full_name: str,
        installation_id: int | None = None,
        config_json: dict[str, Any] | None = None,
    ) -> Repository:
        """Get existing repository or create a new one."""
        stmt = select(Repository).where(
            (Repository.github_repo_id == github_repo_id) | (Repository.full_name == full_name)
        )
        repo = self.session.scalar(stmt)
        if not repo:
            repo = Repository(
                github_repo_id=github_repo_id,
                full_name=full_name,
                installation_id=installation_id,
                config_json=config_json,
            )
            self.session.add(repo)
            self.session.flush()
            logger.info("Created repository record: %s (id=%s)", full_name, repo.id)
        else:
            # Update attributes if changed
            if github_repo_id and repo.github_repo_id != github_repo_id:
                repo.github_repo_id = github_repo_id
            if installation_id and repo.installation_id != installation_id:
                repo.installation_id = installation_id
            if full_name and repo.full_name != full_name:
                repo.full_name = full_name
            self.session.flush()
        return repo

    def get_or_create_pr(
        self,
        repo_id: int,
        number: int,
        title: str = "",
        author: str = "",
        head_sha: str = "",
        base_sha: str = "",
    ) -> PullRequest:
        """Get existing pull request record or create a new one."""
        stmt = select(PullRequest).where(
            PullRequest.repo_id == repo_id,
            PullRequest.number == number,
        )
        pr = self.session.scalar(stmt)
        if not pr:
            pr = PullRequest(
                repo_id=repo_id,
                number=number,
                title=title,
                author=author,
                head_sha=head_sha,
                base_sha=base_sha,
            )
            self.session.add(pr)
            self.session.flush()
            logger.info("Created pull request record: #%s (id=%s)", number, pr.id)
        else:
            pr.title = title or pr.title
            pr.author = author or pr.author
            pr.head_sha = head_sha or pr.head_sha
            pr.base_sha = base_sha or pr.base_sha
            self.session.flush()
        return pr

    def is_already_reviewed(
        self,
        github_repo_id: int,
        pr_number: int,
        head_sha: str,
    ) -> bool:
        """Check if PR at head_sha has already completed review (idempotent guard)."""
        stmt = (
            select(Review)
            .join(PullRequest, Review.pr_id == PullRequest.id)
            .join(Repository, PullRequest.repo_id == Repository.id)
            .where(
                Repository.github_repo_id == github_repo_id,
                PullRequest.number == pr_number,
                Review.head_sha == head_sha,
                Review.status == ReviewStatus.DONE,
            )
        )
        existing = self.session.scalar(stmt)
        return existing is not None

    def create_or_get_review(
        self,
        pr_id: int,
        head_sha: str,
        model: str = "",
        prompt_version: str = "v1",
    ) -> Review:
        """Create new review record in QUEUED state or return existing."""
        stmt = select(Review).where(
            Review.pr_id == pr_id,
            Review.head_sha == head_sha,
        )
        review = self.session.scalar(stmt)
        if not review:
            review = Review(
                pr_id=pr_id,
                head_sha=head_sha,
                status=ReviewStatus.QUEUED,
                model=model,
                prompt_version=prompt_version,
            )
            self.session.add(review)
            self.session.flush()
            logger.info("Created review #%s for PR %s (head: %s)", review.id, pr_id, head_sha)
        return review

    def update_review_status(
        self,
        review_id: int,
        status: ReviewStatus,
        error: str | None = None,
    ) -> None:
        """Update review execution status."""
        stmt = select(Review).where(Review.id == review_id)
        review = self.session.scalar(stmt)
        if review:
            review.status = status
            if error is not None:
                review.error = error
            self.session.flush()
            logger.info("Updated review #%s status to %s", review_id, status.value)

    def complete_review(
        self,
        review_id: int,
        github_review_id: int | None,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        duration_ms: int,
        findings: list[Finding],
    ) -> Review:
        """Finalize review with telemetry and persist individual findings."""
        stmt = select(Review).where(Review.id == review_id)
        review = self.session.scalar(stmt)
        if not review:
            raise ValueError(f"Review #{review_id} not found")

        review.status = ReviewStatus.DONE
        review.github_review_id = github_review_id
        review.input_tokens = input_tokens
        review.output_tokens = output_tokens
        review.cost_usd = cost_usd
        review.duration_ms = duration_ms

        for f in findings:
            finding_model = FindingModel(
                review_id=review_id,
                file_path=f.file,
                line_start=f.line,
                line_end=f.end_line,
                severity=Severity(f.severity),
                category=Category(f.category),
                message=f.message,
                suggestion=f.suggestion,
                confidence=f.confidence,
                evidence=f.evidence,
                posted=True,
            )
            self.session.add(finding_model)

        self.session.flush()
        logger.info(
            "Finalized review #%s: %d findings, %d tokens, cost=$%.4f",
            review_id, len(findings), input_tokens + output_tokens, cost_usd,
        )
        return review

    def save_pr_summary(
        self,
        pr_id: int,
        head_sha: str,
        summary: PRSummary,
        github_comment_id: int | None = None,
    ) -> PRSummaryModel:
        """Save or update PRSummary record."""
        stmt = select(PRSummaryModel).where(
            PRSummaryModel.pr_id == pr_id,
            PRSummaryModel.head_sha == head_sha,
        )
        model = self.session.scalar(stmt)
        changes_formatted = "\n".join(f"- {c}" for c in summary.changes)
        summary_text = f"{summary.summary}\n\nChanges:\n{changes_formatted}"
        risks_text = "\n".join(f"- {r}" for r in summary.risks)
        tests_text = "\n".join(f"- {t}" for t in summary.test_suggestions)

        if not model:
            model = PRSummaryModel(
                pr_id=pr_id,
                head_sha=head_sha,
                summary_md=summary_text,
                risks_md=risks_text,
                test_suggestions_md=tests_text,
                github_comment_id=github_comment_id,
            )
            self.session.add(model)
        else:
            model.summary_md = summary_text
            model.risks_md = risks_text
            model.test_suggestions_md = tests_text
            if github_comment_id:
                model.github_comment_id = github_comment_id

        self.session.flush()
        return model

    def get_review_with_findings(self, review_id: int) -> Review | None:
        """Fetch review with findings eagerly loaded."""
        stmt = (
            select(Review)
            .options(joinedload(Review.findings))
            .where(Review.id == review_id)
        )
        return self.session.scalar(stmt)

    def get_dashboard_stats(self) -> dict[str, Any]:
        """Compute aggregate metrics for the dashboard."""
        total_prs = self.session.scalar(select(func.count(PullRequest.id))) or 0
        total_reviews = self.session.scalar(select(func.count(Review.id))) or 0
        total_findings = self.session.scalar(select(func.count(FindingModel.id))) or 0
        total_tokens = self.session.scalar(
            select(func.coalesce(func.sum(Review.input_tokens + Review.output_tokens), 0))
        ) or 0
        total_cost = self.session.scalar(
            select(func.coalesce(func.sum(Review.cost_usd), 0.0))
        ) or 0.0
        avg_duration = self.session.scalar(
            select(func.coalesce(func.avg(Review.duration_ms), 0))
        ) or 0

        # Severity breakdown
        severities = {s.value: 0 for s in Severity}
        for sev, count in self.session.execute(
            select(FindingModel.severity, func.count(FindingModel.id)).group_by(
                FindingModel.severity
            )
        ):
            sev_key = sev.value if hasattr(sev, "value") else str(sev)
            severities[sev_key] = count

        # Category breakdown
        categories = {c.value: 0 for c in Category}
        for cat, count in self.session.execute(
            select(FindingModel.category, func.count(FindingModel.id)).group_by(
                FindingModel.category
            )
        ):
            cat_key = cat.value if hasattr(cat, "value") else str(cat)
            categories[cat_key] = count

        return {
            "total_prs": total_prs,
            "total_reviews": total_reviews,
            "total_findings": total_findings,
            "total_tokens": int(total_tokens),
            "total_cost_usd": round(float(total_cost), 4),
            "avg_duration_ms": int(avg_duration),
            "severity_breakdown": severities,
            "category_breakdown": categories,
        }

    def get_recent_reviews(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get recent reviews with PR and repo details."""
        stmt = (
            select(Review, PullRequest, Repository, func.count(FindingModel.id))
            .join(PullRequest, Review.pr_id == PullRequest.id)
            .join(Repository, PullRequest.repo_id == Repository.id)
            .outerjoin(FindingModel, Review.id == FindingModel.review_id)
            .group_by(Review.id, PullRequest.id, Repository.id)
            .order_by(Review.id.desc())
            .limit(limit)
        )
        results = []
        for review, pr, repo, count in self.session.execute(stmt):
            results.append({
                "id": review.id,
                "repo_name": repo.full_name,
                "pr_number": pr.number,
                "pr_title": pr.title,
                "author": pr.author,
                "head_sha": review.head_sha[:8],
                "status": review.status.value,
                "model": review.model,
                "findings_count": count,
                "cost_usd": round(review.cost_usd, 4),
                "duration_ms": review.duration_ms,
                "created_at": review.created_at.isoformat() if review.created_at else None,
            })
        return results

    def get_review_detail(self, review_id: int) -> dict[str, Any] | None:
        """Get full details of a review including findings and PR summary."""
        stmt = (
            select(Review, PullRequest, Repository)
            .join(PullRequest, Review.pr_id == PullRequest.id)
            .join(Repository, PullRequest.repo_id == Repository.id)
            .options(joinedload(Review.findings))
            .where(Review.id == review_id)
        )
        row = self.session.execute(stmt).unique().first()
        if not row:
            return None
        review, pr, repo = row

        summary_stmt = select(PRSummaryModel).where(
            PRSummaryModel.pr_id == pr.id,
            PRSummaryModel.head_sha == review.head_sha,
        )
        summary = self.session.scalar(summary_stmt)

        return {
            "id": review.id,
            "repo_name": repo.full_name,
            "pr_number": pr.number,
            "pr_title": pr.title,
            "author": pr.author,
            "head_sha": review.head_sha,
            "status": review.status.value,
            "model": review.model,
            "cost_usd": review.cost_usd,
            "duration_ms": review.duration_ms,
            "input_tokens": review.input_tokens,
            "output_tokens": review.output_tokens,
            "created_at": review.created_at.isoformat() if review.created_at else None,
            "findings": [
                {
                    "id": f.id,
                    "file_path": f.file_path,
                    "line_start": f.line_start,
                    "line_end": f.line_end,
                    "severity": f.severity.value,
                    "category": f.category.value,
                    "message": f.message,
                    "suggestion": f.suggestion,
                    "confidence": f.confidence,
                    "evidence": f.evidence,
                }
                for f in review.findings
            ],
            "summary": {
                "summary_md": summary.summary_md if summary else "",
                "risks_md": summary.risks_md if summary else "",
                "test_suggestions_md": summary.test_suggestions_md if summary else "",
            } if summary else None,
        }

    def get_all_repositories(self) -> list[dict[str, Any]]:
        """Return list of all registered repositories with metrics."""
        repos = list(self.session.scalars(select(Repository).order_by(Repository.id.desc())))
        result: list[dict[str, Any]] = []
        for r in repos:
            pr_count = self.session.scalar(
                select(func.count(PullRequest.id)).where(PullRequest.repo_id == r.id)
            ) or 0
            findings_count = self.session.scalar(
                select(func.count(FindingModel.id))
                .join(Review, FindingModel.review_id == Review.id)
                .join(PullRequest, Review.pr_id == PullRequest.id)
                .where(PullRequest.repo_id == r.id)
            ) or 0
            result.append({
                "id": r.id,
                "github_repo_id": r.github_repo_id,
                "full_name": r.full_name,
                "installation_id": r.installation_id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "prs_count": pr_count,
                "findings_count": findings_count,
                "config": r.config_json or {},
            })
        return result

    def create_repository(
        self,
        full_name: str,
        github_repo_id: int | None = None,
        installation_id: int | None = None,
        config_json: dict[str, Any] | None = None,
    ) -> Repository:
        """Create or update a repository record."""
        repo_id = github_repo_id or (hash(full_name) & 0x7FFFFFFF)
        return self.get_or_create_repo(
            github_repo_id=repo_id,
            full_name=full_name,
            installation_id=installation_id,
            config_json=config_json,
        )

    def delete_repository(self, repo_id: int) -> bool:
        """Delete repository by database id."""
        repo = self.session.get(Repository, repo_id)
        if not repo:
            return False
        self.session.delete(repo)
        self.session.flush()
        return True

    def get_pull_requests(
        self,
        limit: int = 50,
        repo_id: int | None = None,
        state: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return pull requests with review summary metrics."""
        stmt = (
            select(PullRequest, Repository)
            .join(Repository, PullRequest.repo_id == Repository.id)
            .order_by(PullRequest.id.desc())
        )
        if repo_id is not None:
            stmt = stmt.where(PullRequest.repo_id == repo_id)
        if state is not None:
            stmt = stmt.where(PullRequest.state == state)
        stmt = stmt.limit(limit)

        result: list[dict[str, Any]] = []
        for pr, repo in self.session.execute(stmt):
            latest_review = self.session.scalar(
                select(Review)
                .where(Review.pr_id == pr.id)
                .order_by(Review.id.desc())
                .limit(1)
            )
            findings_count = 0
            cost = 0.0
            rev_status = "none"
            rev_id = None
            if latest_review:
                findings_count = self.session.scalar(
                    select(func.count(FindingModel.id))
                    .where(FindingModel.review_id == latest_review.id)
                ) or 0
                cost = latest_review.cost_usd
                rev_status = latest_review.status.value
                rev_id = latest_review.id

            result.append({
                "id": pr.id,
                "number": pr.number,
                "title": pr.title,
                "author": pr.author,
                "head_sha": pr.head_sha[:8],
                "state": pr.state,
                "repo_name": repo.full_name,
                "repo_id": repo.id,
                "created_at": pr.created_at.isoformat() if pr.created_at else None,
                "findings_count": findings_count,
                "latest_review_id": rev_id,
                "latest_review_status": rev_status,
                "cost_usd": round(cost, 4),
            })
        return result

    def get_pr_detail(self, pr_id: int) -> dict[str, Any] | None:
        """Get full details of a PR including its reviews, findings, and summary."""
        stmt = (
            select(PullRequest, Repository)
            .join(Repository, PullRequest.repo_id == Repository.id)
            .where(PullRequest.id == pr_id)
        )
        row = self.session.execute(stmt).first()
        if not row:
            return None
        pr, repo = row

        reviews_stmt = (
            select(Review)
            .options(joinedload(Review.findings))
            .where(Review.pr_id == pr.id)
            .order_by(Review.id.desc())
        )
        reviews = list(self.session.scalars(reviews_stmt).unique())

        summary = self.session.scalar(
            select(PRSummaryModel)
            .where(PRSummaryModel.pr_id == pr.id)
            .order_by(PRSummaryModel.id.desc())
            .limit(1)
        )

        return {
            "id": pr.id,
            "number": pr.number,
            "title": pr.title,
            "author": pr.author,
            "head_sha": pr.head_sha,
            "base_sha": pr.base_sha,
            "state": pr.state,
            "repo_name": repo.full_name,
            "repo_id": repo.id,
            "created_at": pr.created_at.isoformat() if pr.created_at else None,
            "summary": {
                "summary_md": summary.summary_md if summary else "",
                "risks_md": summary.risks_md if summary else "",
                "test_suggestions_md": summary.test_suggestions_md if summary else "",
            } if summary else None,
            "reviews": [
                {
                    "id": rev.id,
                    "head_sha": rev.head_sha,
                    "status": rev.status.value,
                    "model": rev.model,
                    "cost_usd": rev.cost_usd,
                    "duration_ms": rev.duration_ms,
                    "input_tokens": rev.input_tokens,
                    "output_tokens": rev.output_tokens,
                    "findings": [
                        {
                            "id": f.id,
                            "file_path": f.file_path,
                            "line_start": f.line_start,
                            "line_end": f.line_end,
                            "severity": f.severity.value,
                            "category": f.category.value,
                            "message": f.message,
                            "suggestion": f.suggestion,
                            "confidence": f.confidence,
                            "evidence": f.evidence,
                        }
                        for f in rev.findings
                    ],
                }
                for rev in reviews
            ],
        }

    def log_webhook_delivery(
        self,
        delivery_id: str,
        event: str,
        action: str | None = None,
        repo_name: str | None = None,
        status: str = "accepted",
        status_code: int = 202,
        duration_ms: int = 0,
        payload_summary: str | None = None,
        error: str | None = None,
    ) -> WebhookDelivery:
        """Record an incoming webhook delivery for auditing and log dashboard."""
        stmt = select(WebhookDelivery).where(WebhookDelivery.delivery_id == delivery_id)
        existing = self.session.scalar(stmt)
        if existing:
            existing.status = status
            existing.status_code = status_code
            existing.duration_ms = duration_ms
            if error:
                existing.error = error
            self.session.flush()
            return existing

        delivery = WebhookDelivery(
            delivery_id=delivery_id,
            event=event,
            action=action,
            repo_name=repo_name,
            status=status,
            status_code=status_code,
            duration_ms=duration_ms,
            payload_summary=payload_summary,
            error=error,
        )
        self.session.add(delivery)
        self.session.flush()
        return delivery

    def get_recent_webhook_deliveries(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return recent webhook delivery audit records."""
        stmt = (
            select(WebhookDelivery)
            .order_by(WebhookDelivery.id.desc())
            .limit(limit)
        )
        records = list(self.session.scalars(stmt))
        return [
            {
                "id": rec.id,
                "delivery_id": rec.delivery_id,
                "event": rec.event,
                "action": rec.action,
                "repo_name": rec.repo_name,
                "status": rec.status,
                "status_code": rec.status_code,
                "duration_ms": rec.duration_ms,
                "payload_summary": rec.payload_summary,
                "error": rec.error,
                "created_at": rec.created_at.isoformat() if rec.created_at else None,
            }
            for rec in records
        ]

    def get_rule_config(self, config_key: str = "default") -> dict[str, Any]:
        """Fetch saved review policy configuration or return defaults."""
        stmt = select(SystemRuleConfig).where(SystemRuleConfig.config_key == config_key)
        cfg = self.session.scalar(stmt)
        if not cfg:
            return {
                "config_key": config_key,
                "language": "vi",
                "min_confidence": 0.8,
                "post_summary": True,
                "review_drafts": False,
                "severity_threshold": "minor",
                "raw_yaml": (
                    "version: 1\n"
                    "language: vi\n"
                    "rules:\n"
                    "  min_confidence: 0.80\n"
                    "  post_summary: true\n"
                    "  review_drafts: false\n"
                    "  severity_threshold: minor\n"
                ),
            }
        return {
            "config_key": cfg.config_key,
            "language": cfg.language,
            "min_confidence": cfg.min_confidence,
            "post_summary": cfg.post_summary,
            "review_drafts": cfg.review_drafts,
            "severity_threshold": cfg.severity_threshold,
            "raw_yaml": cfg.raw_yaml or "",
            "updated_at": cfg.updated_at.isoformat() if cfg.updated_at else None,
        }

    def save_rule_config(
        self,
        config_data: dict[str, Any],
        config_key: str = "default",
    ) -> dict[str, Any]:
        """Save or update system review policy configuration."""
        stmt = select(SystemRuleConfig).where(SystemRuleConfig.config_key == config_key)
        cfg = self.session.scalar(stmt)
        if not cfg:
            cfg = SystemRuleConfig(
                config_key=config_key,
                language=config_data.get("language", "vi"),
                min_confidence=float(config_data.get("min_confidence", 0.8)),
                post_summary=bool(config_data.get("post_summary", True)),
                review_drafts=bool(config_data.get("review_drafts", False)),
                severity_threshold=config_data.get("severity_threshold", "minor"),
                raw_yaml=config_data.get("raw_yaml"),
            )
            self.session.add(cfg)
        else:
            if "language" in config_data:
                cfg.language = config_data["language"]
            if "min_confidence" in config_data:
                cfg.min_confidence = float(config_data["min_confidence"])
            if "post_summary" in config_data:
                cfg.post_summary = bool(config_data["post_summary"])
            if "review_drafts" in config_data:
                cfg.review_drafts = bool(config_data["review_drafts"])
            if "severity_threshold" in config_data:
                cfg.severity_threshold = config_data["severity_threshold"]
            if "raw_yaml" in config_data:
                cfg.raw_yaml = config_data["raw_yaml"]

        self.session.flush()
        return self.get_rule_config(config_key=config_key)

    def add_feedback(
        self,
        finding_id: int,
        reaction: str,
        source: str = "web",
    ) -> Feedback:
        """Record developer reaction feedback on a review finding."""
        finding = self.session.get(FindingModel, finding_id)
        if not finding:
            raise ValueError(f"Finding #{finding_id} not found")

        rx_val = reaction.lower()
        rx_enum = Reaction(rx_val) if rx_val in [r.value for r in Reaction] else Reaction.POSITIVE
        feedback = Feedback(
            finding_id=finding_id,
            reaction=rx_enum,
            source=source,
        )
        self.session.add(feedback)
        self.session.flush()
        return feedback

    def seed_initial_demo_data(self, force: bool = False) -> None:
        """Seed initial realistic data if DB is empty or force is True."""
        pr_count = self.session.scalar(select(func.count(PullRequest.id))) or 0
        if pr_count > 0 and not force:
            return

        # 1. Repositories
        repo1 = self.get_or_create_repo(
            github_repo_id=1001,
            full_name="vku-se/student-management-app",
        )
        repo2 = self.get_or_create_repo(
            github_repo_id=1002,
            full_name="vku-se/core-library",
        )
        repo3 = self.get_or_create_repo(
            github_repo_id=1003,
            full_name="vku-se/auth-service",
        )

        # 2. PR #101 on repo1
        pr1 = self.get_or_create_pr(
            repo_id=repo1.id,
            number=101,
            title="feat(auth): add database user authentication logic",
            author="vuminh",
            head_sha="e8f9a12c4b5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f",
        )
        rev1 = self.create_or_get_review(
            pr_id=pr1.id,
            head_sha=pr1.head_sha,
            model="claude-sonnet-4-6",
        )
        findings1 = [
            Finding(
                file="src/auth/database.py",
                line=18,
                end_line=19,
                severity="critical",
                category="security",
                message=(
                    "Phát hiện lỗ hổng SQL Injection nghiêm trọng do nối chuỗi trực tiếp "
                    "tham số username và password vào câu lệnh SQL."
                ),
                evidence=(
                    'query = f"SELECT * FROM users WHERE username = '
                    "'{username}' AND password = '{password}'\""
                ),
                suggestion=(
                    'query = "SELECT * FROM users WHERE username = %s AND password = %s"\n'
                    "    cursor.execute(query, (username, password))"
                ),
                confidence=0.98,
            ),
            Finding(
                file="src/auth/database.py",
                line=15,
                end_line=None,
                severity="critical",
                category="security",
                message=(
                    "Không được lưu cứng khóa truy cập AWS trong mã nguồn. "
                    "Cần chuyển sang sử dụng biến môi trường."
                ),
                evidence='AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"',
                suggestion=(
                    "import os\n"
                    "    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')"
                ),
                confidence=0.95,
            ),
        ]
        self.complete_review(
            review_id=rev1.id,
            github_review_id=100101,
            input_tokens=850,
            output_tokens=320,
            cost_usd=0.0074,
            duration_ms=620,
            findings=findings1,
        )
        self.save_pr_summary(
            pr_id=pr1.id,
            head_sha=pr1.head_sha,
            summary=PRSummary(
                title_suggestion="feat(auth): secure user authentication query",
                summary=(
                    "Pull Request bổ sung logic xác thực người dùng trong database "
                    "và kết nối AWS."
                ),
                changes=[
                    "Bổ sung hàm authenticate_user truy vấn bảng users",
                    "Thêm khóa kết nối AWS credentials",
                ],
                risks=[
                    "Nguy cơ SQL Injection khi nối chuỗi trực tiếp",
                    "Hardcoded AWS Access Key lộ lọt thông tin nhạy cảm",
                ],
                test_suggestions=[
                    "Kiểm thử bảo mật SQLi với username: ' OR '1'='1",
                    "Chuyển AWS credentials sang .env",
                ],
            ),
            github_comment_id=900101,
        )

        # 3. PR #102 on repo2
        pr2 = self.get_or_create_pr(
            repo_id=repo2.id,
            number=45,
            title="fix(payment): resolve potential zero division bug in coupon calculation",
            author="linhdan",
            head_sha="a1b2c3d4e5f67890123456789abcdef012345678",
        )
        rev2 = self.create_or_get_review(
            pr_id=pr2.id,
            head_sha=pr2.head_sha,
            model="claude-sonnet-4-6",
        )
        findings2 = [
            Finding(
                file="src/payment/processor.py",
                line=23,
                end_line=None,
                severity="major",
                category="bug",
                message=(
                    "Nguy cơ lỗi ZeroDivisionError nếu tham số coupon_count bằng 0, "
                    "có thể gây crash ứng dụng thanh toán."
                ),
                evidence="discount_ratio = total_amount / coupon_count",
                suggestion=(
                    "if not coupon_count:\n"
                    "        return 0.0\n"
                    "    discount_ratio = total_amount / coupon_count"
                ),
                confidence=0.92,
            )
        ]
        self.complete_review(
            review_id=rev2.id,
            github_review_id=100102,
            input_tokens=620,
            output_tokens=180,
            cost_usd=0.0045,
            duration_ms=450,
            findings=findings2,
        )

        # 4. PR #103 on repo3
        pr3 = self.get_or_create_pr(
            repo_id=repo3.id,
            number=12,
            title="refactor(core): migrate legacy threadpool to async event loop",
            author="hoangnam",
            head_sha="f7e6d5c4b3a2109876543210fedcba9876543210",
        )
        rev3 = self.create_or_get_review(
            pr_id=pr3.id,
            head_sha=pr3.head_sha,
            model="claude-sonnet-4-6",
        )
        findings3 = [
            Finding(
                file="src/auth/service.py",
                line=48,
                end_line=50,
                severity="minor",
                category="performance",
                message=(
                    "Có thể tối ưu hóa kết nối Redis bằng ConnectionPool thay vì "
                    "khởi tạo socket mới mỗi request."
                ),
                evidence="client = redis.Redis(host='localhost')",
                suggestion="client = redis.Redis(connection_pool=pool)",
                confidence=0.88,
            )
        ]
        self.complete_review(
            review_id=rev3.id,
            github_review_id=100103,
            input_tokens=710,
            output_tokens=210,
            cost_usd=0.0052,
            duration_ms=510,
            findings=findings3,
        )

        # 5. Webhook Deliveries
        self.log_webhook_delivery(
            delivery_id="del_7f9a12c4-8e3b-41d2-9a3c",
            event="pull_request",
            action="opened",
            repo_name=repo1.full_name,
            status="accepted",
            status_code=202,
            duration_ms=85,
            payload_summary="PR #101 opened by vuminh",
        )
        self.log_webhook_delivery(
            delivery_id="del_8e3b41d2-9a3c-4e8f-7f9a",
            event="pull_request",
            action="synchronize",
            repo_name=repo2.full_name,
            status="accepted",
            status_code=202,
            duration_ms=110,
            payload_summary="PR #45 head sha updated to a1b2c3d4",
        )
        self.log_webhook_delivery(
            delivery_id="del_1a9c33e8-5d2e-4b6a-9f8e",
            event="ping",
            action=None,
            repo_name=repo3.full_name,
            status="accepted",
            status_code=200,
            duration_ms=18,
            payload_summary="GitHub webhook ping handshake",
        )

        # 6. Default Rule Config
        self.save_rule_config(
            {
                "language": "vi",
                "min_confidence": 0.8,
                "post_summary": True,
                "review_drafts": False,
                "severity_threshold": "minor",
                "raw_yaml": (
                    "version: 1\\n"
                    "language: vi\\n"
                    "rules:\\n"
                    "  min_confidence: 0.80\\n"
                    "  post_summary: true\\n"
                    "  review_drafts: false\\n"
                    "  severity_threshold: minor\\n"
                ),
            }
        )

        self.session.flush()
        logger.info("Database initialized with rich sample demo records successfully.")

