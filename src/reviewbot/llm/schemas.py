"""Pydantic schemas for LLM inputs and structured outputs."""

from typing import Literal

from pydantic import BaseModel, Field


class Finding(BaseModel):
    """An issue or suggestion identified by the LLM reviewer."""

    file: str = Field(description="Relative path to the modified file")
    line: int = Field(description="Line number in the NEW file (right side of diff)")
    end_line: int | None = Field(
        default=None,
        description="End line number if this finding spans multiple lines",
    )
    severity: Literal["critical", "major", "minor", "info"] = Field(
        description="Severity level of the issue",
    )
    category: Literal[
        "bug",
        "security",
        "performance",
        "maintainability",
        "style",
        "test",
    ] = Field(
        description="Category classification of the finding",
    )
    message: str = Field(description="Concise description of the problem and why it matters")
    evidence: str = Field(description="Quoted code snippet or line demonstrating the issue")
    suggestion: str | None = Field(
        default=None,
        description="Recommended replacement code block (if applicable)",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0",
    )


class ReviewResult(BaseModel):
    """Collection of findings and high-level review notes for a chunk or file."""

    findings: list[Finding] = Field(default_factory=list)
    overall_notes: str | None = Field(
        default=None,
        description="Optional brief observation on the changes in this chunk",
    )


class PRSummary(BaseModel):
    """High-level pull request summary, risk assessment, and test recommendations."""

    title_suggestion: str = Field(
        description="Suggested standardized PR title if current title is vague",
    )
    summary: str = Field(description="Concise overview of what this PR introduces or changes")
    changes: list[str] = Field(
        default_factory=list,
        description="Bulleted highlights of primary technical modifications",
    )
    risks: list[str] = Field(
        default_factory=list,
        description="Potential risks, edge cases, or backwards-incompatible impacts",
    )
    test_suggestions: list[str] = Field(
        default_factory=list,
        description="Actionable verification and testing scenarios",
    )
