"""Unit tests for LLM Reviewer, schemas, and retry logic using a fake LLMClient."""

from typing import Any

import pytest

from reviewbot.core.chunker import DiffChunk
from reviewbot.llm.anthropic_client import calculate_cost
from reviewbot.llm.base import LLMClient, LLMResponse
from reviewbot.llm.reviewer import extract_json_payload, review_chunk, summarize_pr
from reviewbot.llm.schemas import PRSummary


class FakeLLMClient(LLMClient):
    """Fake LLM client returning scripted responses for testing."""

    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.call_count = 0
        self.history: list[dict[str, Any]] = []

    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        _max_tokens: int | None = None,
    ) -> LLMResponse:
        self.call_count += 1
        content = self.responses.pop(0) if self.responses else "{}"
        self.history.append({"system": system_prompt, "user": user_prompt})
        return LLMResponse(
            content=content,
            input_tokens=100,
            output_tokens=50,
            estimated_cost_usd=0.001,
            model="fake-claude",
            duration_ms=250,
        )


def test_calculate_cost() -> None:
    # 1M input ($3) + 1M output ($15) = $18
    cost = calculate_cost(1_000_000, 1_000_000)
    assert cost == 18.0

    cost_small = calculate_cost(1000, 500)
    assert cost_small > 0.0


def test_extract_json_payload() -> None:
    # Raw JSON
    assert extract_json_payload('{"a": 1}') == '{"a": 1}'
    # Markdown fence
    assert extract_json_payload('```json\n{"b": 2}\n```') == '{"b": 2}'
    assert extract_json_payload('```\n{"c": 3}\n```') == '{"c": 3}'


@pytest.mark.asyncio
async def test_review_chunk_success() -> None:
    json_response = """
    {
        "findings": [
            {
                "file": "app/main.py",
                "line": 42,
                "end_line": null,
                "severity": "critical",
                "category": "security",
                "message": "SQL Injection vulnerability in query string concatenation",
                "evidence": "query = f'SELECT * FROM users WHERE id = {user_id}'",
                "suggestion": "query = 'SELECT * FROM users WHERE id = %s'",
                "confidence": 0.95
            }
        ],
        "overall_notes": "Security concern identified."
    }
    """
    fake_client = FakeLLMClient([json_response])
    chunk = DiffChunk(
        file_path="app/main.py",
        numbered_diff="+L42: + query = f'SELECT * FROM users WHERE id = {user_id}'",
        start_line=40,
        end_line=45,
        estimated_tokens=50,
        hunks=[],
    )

    result, telemetry = await review_chunk(
        llm_client=fake_client,
        chunk=chunk,
        pr_title="Fix user fetch",
        pr_description="Updates user query",
    )

    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.file == "app/main.py"
    assert finding.line == 42
    assert finding.severity == "critical"
    assert finding.category == "security"
    assert finding.confidence == 0.95
    assert telemetry.model == "fake-claude"
    assert telemetry.input_tokens == 100
    assert fake_client.call_count == 1


@pytest.mark.asyncio
async def test_review_chunk_retry_on_invalid_json() -> None:
    # First response is invalid prose; second is valid JSON
    bad_response = "I found an issue: line 42 has a bug but I didn't return JSON."
    good_response = """
    {
        "findings": [
            {
                "file": "calc.py",
                "line": 15,
                "severity": "major",
                "category": "bug",
                "message": "Division by zero risk",
                "evidence": "return a / b",
                "suggestion": "if b == 0: raise ValueError()",
                "confidence": 0.9
            }
        ]
    }
    """
    fake_client = FakeLLMClient([bad_response, good_response])
    chunk = DiffChunk(
        file_path="calc.py",
        numbered_diff="+L15: + return a / b",
        start_line=10,
        end_line=20,
        estimated_tokens=30,
        hunks=[],
    )

    result, telemetry = await review_chunk(
        llm_client=fake_client,
        chunk=chunk,
        pr_title="Add division",
        pr_description="Implements division logic",
    )

    assert fake_client.call_count == 2
    assert len(result.findings) == 1
    assert result.findings[0].line == 15
    # Telemetry should accumulate 2 calls: 100 + 100 = 200 input tokens
    assert telemetry.input_tokens == 200
    assert telemetry.output_tokens == 100


@pytest.mark.asyncio
async def test_review_chunk_exhaust_retries_raises() -> None:
    bad_response_1 = "invalid json 1"
    bad_response_2 = "invalid json 2"
    bad_response_3 = "invalid json 3"
    fake_client = FakeLLMClient([bad_response_1, bad_response_2, bad_response_3])

    chunk = DiffChunk(
        file_path="bad.py",
        numbered_diff="+L1: + pass",
        start_line=1,
        end_line=2,
        estimated_tokens=10,
        hunks=[],
    )

    with pytest.raises(ValueError, match="Failed to obtain valid JSON"):
        await review_chunk(
            llm_client=fake_client,
            chunk=chunk,
            pr_title="Title",
            pr_description="Desc",
        )
    assert fake_client.call_count == 3


@pytest.mark.asyncio
async def test_summarize_pr() -> None:
    summary_json = """
    {
        "title_suggestion": "feat: introduce JWT authentication",
        "summary": "This PR integrates JWT based authentication.",
        "changes": ["Added auth.py", "Updated login route"],
        "risks": ["Tokens expire in 10 minutes"],
        "test_suggestions": ["Test with expired token", "Test invalid signature"]
    }
    """
    fake_client = FakeLLMClient([summary_json])
    summary, telemetry = await summarize_pr(
        llm_client=fake_client,
        pr_title="add auth",
        pr_description="adds token auth",
        diff_overview="1 file changed: src/auth.py (+50, -0)",
        output_language="vi",
    )

    assert isinstance(summary, PRSummary)
    assert summary.title_suggestion == "feat: introduce JWT authentication"
    assert len(summary.changes) == 2
    assert len(summary.test_suggestions) == 2
    assert telemetry.duration_ms == 250
