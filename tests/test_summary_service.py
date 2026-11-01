"""Unit tests for SummaryService and summary markdown formatting."""

from unittest.mock import AsyncMock

import pytest

from reviewbot.config import Settings
from reviewbot.github.client import GitHubClient
from reviewbot.llm.base import LLMClient, LLMResponse
from reviewbot.llm.schemas import PRSummary
from reviewbot.services.summary_service import SummaryService, format_pr_summary_markdown


class FakeSummaryLLM(LLMClient):
    """Fake LLM client returning PRSummary JSON."""

    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        _ = (system_prompt, user_prompt, max_tokens)
        content = """
        {
            "title_suggestion": "feat: optimize database queries",
            "summary": "This PR adds missing database indexes.",
            "changes": ["Add index on users.email", "Fix slow query"],
            "risks": ["Migration lock during deployment"],
            "test_suggestions": ["Run migration on staging", "Benchmark query time"]
        }
        """
        return LLMResponse(
            content=content,
            input_tokens=150,
            output_tokens=75,
            estimated_cost_usd=0.001,
            model="fake-model",
            duration_ms=300,
        )


def test_format_pr_summary_markdown_vi() -> None:
    summary = PRSummary(
        title_suggestion="fix: resolve memory leak",
        summary="Sửa rò rỉ bộ nhớ trong connection pool.",
        changes=["Đóng connection sau khi query"],
        risks=["Không có"],
        test_suggestions=["Chạy load test 1000 requests"],
    )
    md = format_pr_summary_markdown(summary, language="vi")
    assert GitHubClient.SUMMARY_MARKER in md
    assert "## 🤖 ReviewBot Pull Request Summary" in md
    assert "**💡 Gợi ý tiêu đề PR:** `fix: resolve memory leak`" in md
    assert "### 📌 Tóm tắt (Summary)" in md
    assert "- Đóng connection sau khi query" in md


def test_format_pr_summary_markdown_en() -> None:
    summary = PRSummary(
        title_suggestion="fix: resolve memory leak",
        summary="Fixes memory leak in connection pool.",
        changes=["Close connections after query"],
        risks=["None"],
        test_suggestions=["Run load test"],
    )
    md = format_pr_summary_markdown(summary, language="en")
    assert "**💡 Suggested Title:**" in md
    assert "### 📌 Summary" in md


@pytest.mark.asyncio
async def test_generate_and_post_summary() -> None:
    fake_llm = FakeSummaryLLM()
    service = SummaryService(llm_client=fake_llm, settings=Settings(OUTPUT_LANGUAGE="vi"))

    mock_gh = AsyncMock(spec=GitHubClient)
    mock_gh.upsert_issue_comment = AsyncMock(return_value={"id": 1234})

    summary, tele, comment_res = await service.generate_and_post_summary(
        github_client=mock_gh,
        repo_full_name="owner/repo",
        pr_number=5,
        pr_title="Optimize DB",
        pr_description="Slow queries fix",
        diff_overview="1 file changed",
    )

    assert summary.title_suggestion == "feat: optimize database queries"
    assert tele.input_tokens == 150
    assert comment_res["id"] == 1234

    mock_gh.upsert_issue_comment.assert_called_once()
    call_args = mock_gh.upsert_issue_comment.call_args[1]
    assert call_args["repo_full_name"] == "owner/repo"
    assert call_args["pr_number"] == 5
    assert GitHubClient.SUMMARY_MARKER in call_args["body"]
