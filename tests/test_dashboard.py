"""Tests for ReviewBot web dashboard and metrics API."""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from reviewbot.config import Settings
from reviewbot.db.session import create_all_tables, reset_engine
from reviewbot.main import app


@pytest.fixture(autouse=True)
def init_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    test_db = tmp_path / "test_dash.db"
    sqlite_url = f"sqlite:///{test_db}"
    monkeypatch.setenv("DATABASE_URL", sqlite_url)
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "test-secret")
    test_settings = Settings(
        DATABASE_URL=sqlite_url,
        GITHUB_WEBHOOK_SECRET="test-secret",
    )
    monkeypatch.setattr("reviewbot.config.get_settings", lambda: test_settings)
    monkeypatch.setattr("reviewbot.db.session.get_settings", lambda: test_settings)
    reset_engine()
    create_all_tables()
    return test_settings


@pytest.mark.asyncio
async def test_dashboard_home_page() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "ReviewBot" in response.text


@pytest.mark.asyncio
async def test_dashboard_stats_and_reviews_empty() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Stats
        stats_resp = await client.get("/api/dashboard/stats")
        assert stats_resp.status_code == 200
        stats = stats_resp.json()
        assert "total_prs" in stats
        assert "severity_breakdown" in stats
        assert "category_breakdown" in stats

        # Reviews
        reviews_resp = await client.get("/api/dashboard/reviews")
        assert reviews_resp.status_code == 200
        assert isinstance(reviews_resp.json(), list)


@pytest.mark.asyncio
async def test_dashboard_simulate_and_detail() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "filename": "src/auth/database.py",
            "title": "feat: test sql injection",
            "patch": """@@ -15,7 +15,10 @@ def authenticate_user(username, password):
-    # TODO: verify user
-    return None
+    AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"
+    # Querying user with raw SQL string formatting
+    query = f"SELECT * FROM users WHERE username = '{username}' AND password = '{password}'"
+    cursor.execute(query)
+    return cursor.fetchone()
""",
            "description": "test PR",
        }
        sim_resp = await client.post("/api/dashboard/simulate", json=payload)
        assert sim_resp.status_code == 200
        sim_data = sim_resp.json()
        assert sim_data["status"] == "success"
        assert len(sim_data["findings"]) > 0
        assert "summary" in sim_data

        # Check that it appeared in recent reviews
        reviews_resp = await client.get("/api/dashboard/reviews")
        assert reviews_resp.status_code == 200
        reviews = reviews_resp.json()
        assert len(reviews) > 0
        latest_id = reviews[0]["id"]

        # Detail endpoint
        detail_resp = await client.get(f"/api/dashboard/reviews/{latest_id}")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert detail["id"] == latest_id
        assert len(detail["findings"]) > 0


@pytest.mark.asyncio
async def test_dashboard_repositories_and_prs() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create a repository
        repo_resp = await client.post(
            "/api/dashboard/repositories",
            json={"full_name": "test-org/new-repo", "installation_id": 1234},
        )
        assert repo_resp.status_code == 201
        repo_data = repo_resp.json()
        assert repo_data["status"] == "success"
        repo_id = repo_data["repository"]["id"]

        # 2. List repositories
        list_resp = await client.get("/api/dashboard/repositories")
        assert list_resp.status_code == 200
        repos = list_resp.json()
        assert any(r["full_name"] == "test-org/new-repo" for r in repos)

        # 3. List PRs
        prs_resp = await client.get("/api/dashboard/pull-requests")
        assert prs_resp.status_code == 200
        assert isinstance(prs_resp.json(), list)

        # 4. Delete repository
        del_resp = await client.delete(f"/api/dashboard/repositories/{repo_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "success"


@pytest.mark.asyncio
async def test_dashboard_webhooks_and_config() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Fetch webhooks
        wh_resp = await client.get("/api/dashboard/webhooks")
        assert wh_resp.status_code == 200
        assert isinstance(wh_resp.json(), list)

        # 2. Get rule config
        cfg_resp = await client.get("/api/dashboard/config")
        assert cfg_resp.status_code == 200
        cfg = cfg_resp.json()
        assert "language" in cfg

        # 3. Update rule config
        update_resp = await client.post(
            "/api/dashboard/config",
            json={
                "language": "en",
                "min_confidence": 0.85,
                "post_summary": True,
                "review_drafts": False,
                "severity_threshold": "major",
            },
        )
        assert update_resp.status_code == 200
        updated = update_resp.json()
        assert updated["config"]["language"] == "en"
        assert updated["config"]["min_confidence"] == 0.85


@pytest.mark.asyncio
async def test_dashboard_benchmark_api() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Get benchmark report
        bench_resp = await client.get("/api/dashboard/benchmark")
        assert bench_resp.status_code == 200
        data = bench_resp.json()
        assert "precision" in data
        assert "recall" in data
        assert "f1_score" in data
        assert "cases" in data

        # 2. Run benchmark suite
        run_resp = await client.post("/api/dashboard/benchmark/run")
        assert run_resp.status_code == 200
        run_data = run_resp.json()
        assert run_data["status"] == "success"
        assert "markdown_table" in run_data
        assert run_data["report"]["precision"] >= 0.85

