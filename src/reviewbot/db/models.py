"""SQLAlchemy 2.0 data models for ReviewBot."""

import enum
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy declarative models."""

    # Map generic JSON to JSONB on PostgreSQL if available, otherwise standard JSON
    type_annotation_map = {
        dict[str, Any]: JSON().with_variant(JSONB, "postgresql"),
    }


def utcnow() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(UTC)


class ReviewStatus(enum.StrEnum):
    """Status lifecycle of a PR review."""

    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class Severity(enum.StrEnum):
    """Issue severity level."""

    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    INFO = "info"


class Category(enum.StrEnum):
    """Issue domain category."""

    BUG = "bug"
    SECURITY = "security"
    PERFORMANCE = "performance"
    MAINTAINABILITY = "maintainability"
    STYLE = "style"
    TEST = "test"


class Reaction(enum.StrEnum):
    """Developer feedback reaction on a review comment."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NONE = "none"


class Repository(Base):
    """Monitored GitHub repository."""

    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    github_repo_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    installation_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    config_json: Mapped[dict[str, Any] | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relationships
    pull_requests: Mapped[list["PullRequest"]] = relationship(
        "PullRequest", back_populates="repository", cascade="all, delete-orphan"
    )


class PullRequest(Base):
    """GitHub Pull Request tracked by ReviewBot."""

    __tablename__ = "pull_requests"
    __table_args__ = (UniqueConstraint("repo_id", "number", name="uq_repo_pr_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repo_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), default="")
    author: Mapped[str] = mapped_column(String(100), default="")
    head_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    base_sha: Mapped[str] = mapped_column(String(40), default="")
    state: Mapped[str] = mapped_column(String(20), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    # Relationships
    repository: Mapped["Repository"] = relationship("Repository", back_populates="pull_requests")
    reviews: Mapped[list["Review"]] = relationship(
        "Review", back_populates="pull_request", cascade="all, delete-orphan"
    )
    summaries: Mapped[list["PRSummaryModel"]] = relationship(
        "PRSummaryModel", back_populates="pull_request", cascade="all, delete-orphan"
    )


class Review(Base):
    """Review execution instance for a specific PR commit head."""

    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("pr_id", "head_sha", name="uq_pr_head_sha"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pr_id: Mapped[int] = mapped_column(
        ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=False
    )
    head_sha: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus, name="review_status_enum", native_enum=False),
        default=ReviewStatus.QUEUED,
        nullable=False,
    )
    model: Mapped[str] = mapped_column(String(100), default="")
    prompt_version: Mapped[str] = mapped_column(String(50), default="v1")
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    github_review_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relationships
    pull_request: Mapped["PullRequest"] = relationship("PullRequest", back_populates="reviews")
    findings: Mapped[list["FindingModel"]] = relationship(
        "FindingModel", back_populates="review", cascade="all, delete-orphan"
    )


class FindingModel(Base):
    """Individual code issue found during a review."""

    __tablename__ = "findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_id: Mapped[int] = mapped_column(
        ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False
    )
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    line_start: Mapped[int] = mapped_column(Integer, nullable=False)
    line_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    severity: Mapped[Severity] = mapped_column(
        Enum(Severity, name="severity_enum", native_enum=False),
        nullable=False,
    )
    category: Mapped[Category] = mapped_column(
        Enum(Category, name="category_enum", native_enum=False),
        nullable=False,
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    suggestion: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    evidence: Mapped[str] = mapped_column(Text, default="")
    posted: Mapped[bool] = mapped_column(Boolean, default=True)
    github_comment_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relationships
    review: Mapped["Review"] = relationship("Review", back_populates="findings")
    feedback: Mapped[list["Feedback"]] = relationship(
        "Feedback", back_populates="finding", cascade="all, delete-orphan"
    )


class Feedback(Base):
    """User reaction feedback on a review comment."""

    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    finding_id: Mapped[int] = mapped_column(
        ForeignKey("findings.id", ondelete="CASCADE"), nullable=False
    )
    reaction: Mapped[Reaction] = mapped_column(
        Enum(Reaction, name="reaction_enum", native_enum=False),
        default=Reaction.NONE,
        nullable=False,
    )
    source: Mapped[str] = mapped_column(String(50), default="github")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relationships
    finding: Mapped["FindingModel"] = relationship("FindingModel", back_populates="feedback")


class PRSummaryModel(Base):
    """PR summary markdown persisted for auditing and dashboards."""

    __tablename__ = "pr_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pr_id: Mapped[int] = mapped_column(
        ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=False
    )
    head_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    summary_md: Mapped[str] = mapped_column(Text, nullable=False)
    risks_md: Mapped[str] = mapped_column(Text, default="")
    test_suggestions_md: Mapped[str] = mapped_column(Text, default="")
    github_comment_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relationships
    pull_request: Mapped["PullRequest"] = relationship("PullRequest", back_populates="summaries")


class WebhookDelivery(Base):
    """Audit log of incoming GitHub webhook deliveries."""

    __tablename__ = "webhook_deliveries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    delivery_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    event: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    action: Mapped[str | None] = mapped_column(String(50), nullable=True)
    repo_name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default="accepted", index=True)
    status_code: Mapped[int] = mapped_column(Integer, default=202)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    payload_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SystemRuleConfig(Base):
    """Review policies and configuration rules persisted in database."""

    __tablename__ = "rule_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_key: Mapped[str] = mapped_column(String(100), unique=True, index=True, default="default")
    language: Mapped[str] = mapped_column(String(20), default="vi")
    min_confidence: Mapped[float] = mapped_column(Float, default=0.8)
    post_summary: Mapped[bool] = mapped_column(Boolean, default=True)
    review_drafts: Mapped[bool] = mapped_column(Boolean, default=False)
    severity_threshold: Mapped[str] = mapped_column(String(20), default="minor")
    raw_yaml: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class User(Base):
    """Registered platform user for authentication and authorization."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(100), default="")
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
