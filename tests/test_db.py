"""Unit tests for database models, session management, and repositories."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from reviewbot.db.models import Base, ReviewStatus, Severity
from reviewbot.db.repositories import ReviewRepository
from reviewbot.db.session import create_all_tables, get_db_session
from reviewbot.llm.schemas import Finding, PRSummary
from reviewbot.worker.tasks import run_review_pipeline


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provide isolated in-memory SQLite database session for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    create_all_tables(engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_repo_and_pr_crud(db_session: Session) -> None:
    repo_layer = ReviewRepository(db_session)

    # 1. Create Repository
    repo = repo_layer.get_or_create_repo(
        github_repo_id=12345,
        full_name="octocat/Hello-World",
        installation_id=987,
    )
    assert repo.id is not None
    assert repo.full_name == "octocat/Hello-World"

    # 2. Re-fetch Repository (idempotent get)
    repo2 = repo_layer.get_or_create_repo(
        github_repo_id=12345,
        full_name="octocat/Hello-World",
    )
    assert repo2.id == repo.id

    # 3. Create Pull Request
    pr = repo_layer.get_or_create_pr(
        repo_id=repo.id,
        number=42,
        title="Add feature",
        author="octocat",
        head_sha="head123456",
        base_sha="base123456",
    )
    assert pr.id is not None
    assert pr.number == 42
    assert pr.repository.full_name == "octocat/Hello-World"


def test_review_lifecycle_and_findings(db_session: Session) -> None:
    repo_layer = ReviewRepository(db_session)
    repo = repo_layer.get_or_create_repo(12345, "octocat/Hello-World")
    pr = repo_layer.get_or_create_pr(repo.id, 42, head_sha="sha_abc")

    # 1. Create Review (QUEUED)
    review = repo_layer.create_or_get_review(pr.id, "sha_abc", model="claude-sonnet-4-6")
    assert review.status == ReviewStatus.QUEUED

    # 2. Update to RUNNING
    repo_layer.update_review_status(review.id, ReviewStatus.RUNNING)
    assert review.status == ReviewStatus.RUNNING

    # 3. Complete Review with findings
    findings = [
        Finding(
            file="app/main.py",
            line=10,
            severity="critical",
            category="security",
            message="SQL Injection detected",
            evidence="query = f'SELECT...'",
            suggestion="query = 'SELECT...'",
            confidence=0.95,
        ),
        Finding(
            file="app/main.py",
            line=20,
            severity="minor",
            category="style",
            message="Unused variable",
            evidence="x = 1",
            confidence=0.8,
        ),
    ]

    completed = repo_layer.complete_review(
        review_id=review.id,
        github_review_id=99999,
        input_tokens=1500,
        output_tokens=300,
        cost_usd=0.009,
        duration_ms=1200,
        findings=findings,
    )

    assert completed.status == ReviewStatus.DONE
    assert completed.github_review_id == 99999
    assert completed.cost_usd == 0.009

    # 4. Fetch review with findings
    fetched = repo_layer.get_review_with_findings(review.id)
    assert fetched is not None
    assert len(fetched.findings) == 2
    assert fetched.findings[0].severity == Severity.CRITICAL
    assert fetched.findings[0].file_path == "app/main.py"


def test_idempotency_check(db_session: Session) -> None:
    repo_layer = ReviewRepository(db_session)
    repo = repo_layer.get_or_create_repo(12345, "octocat/Hello-World")
    pr = repo_layer.get_or_create_pr(repo.id, 42, head_sha="sha_done")

    # Before completion: not reviewed
    review = repo_layer.create_or_get_review(pr.id, "sha_done")
    assert repo_layer.is_already_reviewed(12345, 42, "sha_done") is False

    # After completion: already reviewed is True
    repo_layer.complete_review(
        review_id=review.id,
        github_review_id=1,
        input_tokens=100,
        output_tokens=50,
        cost_usd=0.001,
        duration_ms=500,
        findings=[],
    )
    assert repo_layer.is_already_reviewed(12345, 42, "sha_done") is True

    # Different SHA is False
    assert repo_layer.is_already_reviewed(12345, 42, "sha_different") is False


def test_pr_summary_persistence(db_session: Session) -> None:
    repo_layer = ReviewRepository(db_session)
    repo = repo_layer.get_or_create_repo(12345, "octocat/Hello-World")
    pr = repo_layer.get_or_create_pr(repo.id, 42, head_sha="sha_sum")

    summary = PRSummary(
        title_suggestion="feat: new feature",
        summary="Summary text",
        changes=["Change 1", "Change 2"],
        risks=["Risk A"],
        test_suggestions=["Test 1"],
    )

    # 1. Create summary
    model = repo_layer.save_pr_summary(pr.id, "sha_sum", summary, github_comment_id=777)
    assert model.id is not None
    assert model.github_comment_id == 777
    assert "Summary text" in model.summary_md

    # 2. Update existing summary
    summary.summary = "Updated summary text"
    model_updated = repo_layer.save_pr_summary(pr.id, "sha_sum", summary, github_comment_id=888)
    assert model_updated.id == model.id
    assert model_updated.github_comment_id == 888
    assert "Updated summary text" in model_updated.summary_md


@pytest.mark.asyncio
async def test_run_review_pipeline_integration() -> None:
    test_engine = create_engine("sqlite:///:memory:", echo=False)
    create_all_tables(test_engine)
    test_factory = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    payload = {
        "installation_id": 12345,
        "repo_full_name": "owner/repo",
        "pr_number": 1,
        "head_sha": "abc123456",
        "github_repo_id": 99999,
        "pr_title": "PR Title",
        "pr_body": "PR Body",
    }

    mock_service_result = {
        "status": "done",
        "repo": "owner/repo",
        "pr_number": 1,
        "head_sha": "abc123456",
        "findings_count": 0,
        "findings": [],
        "github_review_id": 5555,
        "summary_comment_id": 6666,
        "summary": {
            "title_suggestion": "test",
            "summary": "test",
            "changes": [],
            "risks": [],
            "test_suggestions": [],
        },
        "input_tokens": 100,
        "output_tokens": 50,
        "total_cost_usd": 0.001,
        "duration_ms": 300,
    }

    with (
        patch("reviewbot.worker.tasks.get_db_session", lambda: get_db_session(test_factory)),
        patch(
            "reviewbot.services.review_service.ReviewService.review_pull_request",
            AsyncMock(return_value=mock_service_result),
        ),
    ):
        # 1. First execution -> runs pipeline
        res1 = await run_review_pipeline(payload)
        assert res1["status"] == "done"

        # 2. Second execution with identical payload -> skipped by idempotency
        res2 = await run_review_pipeline(payload)
        assert res2["status"] == "skipped"
        assert res2["message"] == "PR commit already reviewed"


def test_repository_crud_and_seed(db_session: Session) -> None:
    repo_layer = ReviewRepository(db_session)

    # 1. Seed demo data
    repo_layer.seed_initial_demo_data(force=True)

    # 2. Check repositories
    repos = repo_layer.get_all_repositories()
    assert len(repos) >= 3
    names = [r["full_name"] for r in repos]
    assert "vku-se/student-management-app" in names

    # 3. Check pull requests
    prs = repo_layer.get_pull_requests()
    assert len(prs) >= 3
    assert prs[0]["number"] in [101, 45, 12]

    # 4. Check PR detail
    pr_id = prs[0]["id"]
    detail = repo_layer.get_pr_detail(pr_id)
    assert detail is not None
    assert "reviews" in detail

    # 5. Delete repo
    repo_to_del = repo_layer.create_repository("temp/delete-me")
    assert repo_layer.delete_repository(repo_to_del.id) is True
    assert repo_layer.delete_repository(999999) is False


def test_webhook_delivery_logging(db_session: Session) -> None:
    repo_layer = ReviewRepository(db_session)
    delivery = repo_layer.log_webhook_delivery(
        delivery_id="del_test_123",
        event="pull_request",
        action="opened",
        repo_name="org/repo",
        status="accepted",
        status_code=202,
        duration_ms=45,
        payload_summary="Test payload",
    )
    assert delivery.id is not None
    assert delivery.delivery_id == "del_test_123"

    # List deliveries
    logs = repo_layer.get_recent_webhook_deliveries()
    assert any(log["delivery_id"] == "del_test_123" for log in logs)


def test_rule_config_and_feedback(db_session: Session) -> None:
    repo_layer = ReviewRepository(db_session)

    # 1. Config CRUD
    cfg = repo_layer.get_rule_config()
    assert cfg["language"] in ["vi", "en"]

    updated = repo_layer.save_rule_config({"language": "en", "min_confidence": 0.9})
    assert updated["language"] == "en"
    assert updated["min_confidence"] == 0.9

    # 2. Feedback
    repo = repo_layer.get_or_create_repo(1234, "test/feedback-repo")
    pr = repo_layer.get_or_create_pr(repo.id, 1, head_sha="sha_fb")
    rev = repo_layer.create_or_get_review(pr.id, "sha_fb")
    f_model = Finding(
        file="test.py",
        line=1,
        severity="minor",
        category="style",
        message="style issue",
        evidence="x=1",
        confidence=0.8,
    )
    completed = repo_layer.complete_review(
        review_id=rev.id,
        github_review_id=1,
        input_tokens=10,
        output_tokens=10,
        cost_usd=0.0001,
        duration_ms=100,
        findings=[f_model],
    )
    finding_id = completed.findings[0].id
    fb = repo_layer.add_feedback(finding_id, reaction="positive", source="web")
    assert fb.id is not None
    assert fb.reaction.value == "positive"

