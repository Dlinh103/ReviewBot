"""Unit and integration tests for User Authentication and Auth API router."""

from pathlib import Path

import pytest
from fastapi import HTTPException, Response

from reviewbot.api.auth import (
    COOKIE_NAME,
    LoginRequest,
    RegisterRequest,
    UpdateProfileRequest,
    get_me,
    login,
    logout,
    register,
    serve_login_page,
    serve_register_page,
    update_profile,
)
from reviewbot.api.dashboard import (
    export_audit_report,
    get_analytics,
    retry_webhook_delivery,
    toggle_repository,
)
from reviewbot.config import Settings
from reviewbot.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from reviewbot.db.repositories import ReviewRepository, UserRepository
from reviewbot.db.session import create_all_tables, get_db_session, reset_engine


@pytest.fixture(autouse=True)
def init_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Provide an isolated SQLite database for each test run."""
    test_db = tmp_path / "test_auth.db"
    sqlite_url = f"sqlite:///{test_db}"
    monkeypatch.setenv("DATABASE_URL", sqlite_url)
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "test-secret-long-enough-32-bytes-secure")

    test_settings = Settings(
        DATABASE_URL=sqlite_url,
        GITHUB_WEBHOOK_SECRET="test-secret-long-enough-32-bytes-secure",
    )
    monkeypatch.setattr("reviewbot.config.get_settings", lambda: test_settings)
    monkeypatch.setattr("reviewbot.db.session.get_settings", lambda: test_settings)
    monkeypatch.setattr("reviewbot.core.security.get_settings", lambda: test_settings)

    reset_engine()
    create_all_tables()
    return test_settings


def test_password_hashing() -> None:
    """Verify PBKDF2 password hashing and verification."""
    password = "SuperSecretPassword@2026"
    hashed = hash_password(password)

    assert hashed.startswith("pbkdf2_sha256$100000$")
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword@123", hashed) is False
    assert verify_password("", hashed) is False
    assert verify_password(password, "") is False

    # Unique salts produce different hashes for same password
    hashed2 = hash_password(password)
    assert hashed != hashed2
    assert verify_password(password, hashed2) is True


def test_jwt_token_creation_and_decoding() -> None:
    """Verify JWT access token creation and payload decoding."""
    payload = {"sub": "42", "username": "alice", "is_superuser": False}
    token = create_access_token(payload)

    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == "42"
    assert decoded["username"] == "alice"
    assert decoded["iss"] == "reviewbot-api"

    # Invalid token handling
    assert decode_access_token("invalid.token.signature") is None


def test_user_repository_crud_and_auth() -> None:
    """Verify UserRepository methods: create, authenticate, profile update."""
    with get_db_session() as session:
        repo = UserRepository(session)

        # 1. Create user
        user = repo.create_user(
            username="john_doe",
            email="john@example.com",
            password="Password@123",
            full_name="John Doe",
        )
        assert user.id is not None
        assert user.username == "john_doe"

        # 2. Duplicate username / email check
        with pytest.raises(ValueError, match="đã tồn tại"):
            repo.create_user(
                username="john_doe",
                email="other@example.com",
                password="Password@123",
            )

        with pytest.raises(ValueError, match="đã được đăng ký"):
            repo.create_user(
                username="another_user",
                email="john@example.com",
                password="Password@123",
            )

        # 3. Authenticate with username and email
        auth1 = repo.authenticate("john_doe", "Password@123")
        assert auth1 is not None
        assert auth1.id == user.id

        auth2 = repo.authenticate("john@example.com", "Password@123")
        assert auth2 is not None

        assert repo.authenticate("john_doe", "WrongPass") is None
        assert repo.authenticate("unknown_user", "Password@123") is None

        # 4. Update profile
        updated = repo.update_profile(
            user.id,
            full_name="Jonathan Doe",
            new_password="NewPassword@456",
        )
        assert updated is not None
        assert updated.full_name == "Jonathan Doe"
        assert repo.authenticate("john_doe", "NewPassword@456") is not None
        assert repo.authenticate("john_doe", "Password@123") is None


def test_auth_api_register_and_login_flow() -> None:
    """Test register, login, me, profile update, and logout endpoints."""
    resp = Response()

    # 1. Register new user
    reg_req = RegisterRequest(
        username="minh_vku",
        email="minh@vku.udn.vn",
        password="Password@789",
        full_name="Nguyễn Văn Minh",
    )
    reg_data = register(reg_req, resp)
    assert reg_data["status"] == "success"
    assert "access_token" in reg_data
    assert reg_data["user"]["username"] == "minh_vku"
    assert reg_data["user"]["email"] == "minh@vku.udn.vn"

    # Verify cookie was set on response
    assert COOKIE_NAME in resp.headers.get("set-cookie", "")

    # 2. Login with registered user credentials
    login_resp = Response()
    login_req = LoginRequest(identifier="minh_vku", password="Password@789")
    login_data = login(login_req, login_resp)
    assert login_data["status"] == "success"
    assert "access_token" in login_data
    assert login_data["user"]["username"] == "minh_vku"

    # 3. Login with invalid password -> HTTPException 401
    bad_login_req = LoginRequest(identifier="minh_vku", password="IncorrectPassword")
    with pytest.raises(HTTPException) as exc_info:
        login(bad_login_req, Response())
    assert exc_info.value.status_code == 401

    # 4. Get me and update profile
    with get_db_session() as session:
        user_repo = UserRepository(session)
        current_user = user_repo.get_by_username("minh_vku")
        assert current_user is not None

    me_data = get_me(current_user)
    assert me_data["user"]["username"] == "minh_vku"

    update_req = UpdateProfileRequest(full_name="Minh Nguyễn VIP")
    updated_data = update_profile(update_req, current_user)
    assert updated_data["user"]["full_name"] == "Minh Nguyễn VIP"

    # 5. Logout
    logout_resp = Response()
    logout_data = logout(logout_resp)
    assert logout_data["status"] == "success"


def test_demo_user_seeded() -> None:
    """Verify default demo user 'vu_admin' is seeded automatically."""
    with get_db_session() as session:
        rev_repo = ReviewRepository(session)
        rev_repo.seed_initial_demo_data(force=True)

        user_repo = UserRepository(session)
        demo_user = user_repo.authenticate("vu_admin", "Admin@123456")
        assert demo_user is not None
        assert demo_user.email == "admin@vku.udn.vn"
        assert demo_user.full_name == "Vũ Nguyễn"
        assert demo_user.is_superuser is True


def test_auth_pages_serve_html() -> None:
    """Verify serve_login_page and serve_register_page return HTML response."""
    res_login = serve_login_page()
    assert res_login.status_code == 200
    login_body = bytes(res_login.body).decode("utf-8")
    assert "ReviewBot" in login_body
    assert "tab-login" in login_body

    res_reg = serve_register_page()
    assert res_reg.status_code == 200
    reg_body = bytes(res_reg.body).decode("utf-8")
    assert "tab-register" in reg_body


def test_extended_backend_endpoints() -> None:
    """Verify backend features: export audit report, toggle repo, retry webhook, analytics."""
    with get_db_session() as session:
        rev_repo = ReviewRepository(session)
        rev_repo.seed_initial_demo_data(force=True)
        repos = rev_repo.get_all_repositories()
        delivs = rev_repo.get_recent_webhook_deliveries()

    repo_id = repos[0]["id"]
    deliv_id = delivs[0]["delivery_id"]

    # 1. Export audit report (JSON)
    rep_data = export_audit_report(format="json")
    assert "title" in rep_data
    assert "critical_findings" in rep_data
    assert "compliance_status" in rep_data

    # 2. Export audit report (Markdown)
    rep_md = export_audit_report(format="markdown")
    assert rep_md.status_code == 200
    assert "text/markdown" in rep_md.headers["content-type"]
    md_text = bytes(rep_md.body).decode("utf-8")
    assert "# ReviewBot AI Code Quality & Security Audit Report" in md_text

    # 3. Analytics
    ana_data = get_analytics()
    assert "engineering_roi" in ana_data
    assert "quality_metrics" in ana_data

    # 4. Toggle repository auto-review
    toggle_data = toggle_repository(repo_id)
    assert toggle_data["status"] == "success"
    assert toggle_data["repository"]["is_active"] is False

    # 5. Retry webhook delivery
    retry_data = retry_webhook_delivery(deliv_id)
    assert retry_data["status"] == "success"
    assert "new_delivery_id" in retry_data
