"""End-to-end unit tests for ReviewService orchestration pipeline."""

from unittest.mock import AsyncMock

import pytest

from reviewbot.config import Settings
from reviewbot.github.client import GitHubClient
from reviewbot.llm.base import LLMClient, LLMResponse
from reviewbot.services.review_service import ReviewService

SAMPLE_PYTHON_PATCH = """@@ -1,4 +1,5 @@
 def divide(a, b):
-    return a / b
+    # Potential division by zero bug
+    return a / b
"""


class MockPipelineLLM(LLMClient):
    """Mock LLM responding appropriately to review and summary prompts."""

    def __init__(self) -> None:
        self.call_count = 0

    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        _ = (user_prompt, max_tokens)
        self.call_count += 1
        if "tóm tắt" in system_prompt.lower() or "summary" in system_prompt.lower():
            content = """
            {
                "title_suggestion": "fix(calc): handle division",
                "summary": "Fixes division function",
                "changes": ["Updated division implementation"],
                "risks": ["Division by zero"],
                "test_suggestions": ["Test with b=0"]
            }
            """
        else:
            # Code review prompt
            content = """
            {
                "findings": [
                    {
                        "file": "calc.py",
                        "line": 3,
                        "severity": "critical",
                        "category": "bug",
                        "message": "Unchecked division by zero when b equals 0",
                        "evidence": "return a / b",
                        "suggestion": "if b == 0:\\n    raise ZeroDivisionError()\\nreturn a / b",
                        "confidence": 0.95
                    }
                ],
                "overall_notes": "Critical bug identified"
            }
            """

        return LLMResponse(
            content=content,
            input_tokens=200,
            output_tokens=100,
            estimated_cost_usd=0.002,
            model="mock-claude",
            duration_ms=400,
        )


@pytest.mark.asyncio
async def test_review_service_end_to_end() -> None:
    # 1. Setup mock GitHub Client
    mock_gh = AsyncMock(spec=GitHubClient)
    # Return 2 files: one python file and one lock file (should be ignored)
    mock_gh.get_pr_files = AsyncMock(
        return_value=[
            {
                "filename": "calc.py",
                "status": "modified",
                "changes": 3,
                "patch": SAMPLE_PYTHON_PATCH,
            },
            {
                "filename": "poetry.lock",
                "status": "modified",
                "changes": 100,
                "patch": "@@ -1,5 +1,5 @@ lock data",
            },
        ]
    )
    mock_gh.create_review = AsyncMock(return_value={"id": 9999, "state": "COMMENTED"})
    mock_gh.upsert_issue_comment = AsyncMock(return_value={"id": 8888})

    # 2. Setup mock LLM and service
    mock_llm = MockPipelineLLM()
    settings = Settings(
        MIN_CONFIDENCE=0.6,
        MAX_COMMENTS_PER_PR=15,
        OUTPUT_LANGUAGE="vi",
    )
    service = ReviewService(llm_client=mock_llm, settings=settings)

    # 3. Execute review pipeline
    result = await service.review_pull_request(
        github_client=mock_gh,
        repo_full_name="octocat/Hello-World",
        pr_number=42,
        head_sha="6dcb09b5b57875f334f61aebed695e2e4193db5e",
        pr_title="Update division logic",
        pr_body="This PR updates division function in calc.py",
    )

    # 4. Verify results
    assert result["status"] == "done"
    assert result["repo"] == "octocat/Hello-World"
    assert result["pr_number"] == 42
    assert result["findings_count"] == 1
    assert result["github_review_id"] == 9999
    assert result["summary_comment_id"] == 8888
    assert result["total_cost_usd"] > 0
    assert result["duration_ms"] > 0

    # Verify GitHub create_review call
    mock_gh.create_review.assert_called_once()
    review_call_kwargs = mock_gh.create_review.call_args[1]
    assert review_call_kwargs["repo_full_name"] == "octocat/Hello-World"
    assert review_call_kwargs["pr_number"] == 42
    assert review_call_kwargs["commit_id"] == "6dcb09b5b57875f334f61aebed695e2e4193db5e"
    assert "🔴 Critical: 1" in review_call_kwargs["body"]

    # Verify inline comment details
    comments = review_call_kwargs["comments"]
    assert len(comments) == 1
    comment = comments[0]
    assert comment["path"] == "calc.py"
    # Line 3 is on '+    return a / b'
    assert comment["line"] == 3
    assert comment["side"] == "RIGHT"
    assert "🔴 **[CRITICAL]** 🐛 Bug" in comment["body"]
    assert "```suggestion" in comment["body"]

    # Verify GitHub upsert_issue_comment call
    mock_gh.upsert_issue_comment.assert_called_once()
    comment_call_kwargs = mock_gh.upsert_issue_comment.call_args[1]
    assert GitHubClient.SUMMARY_MARKER in comment_call_kwargs["body"]
    assert "fix(calc): handle division" in comment_call_kwargs["body"]
