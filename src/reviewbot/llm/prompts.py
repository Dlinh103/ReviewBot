"""System and user prompt templates for LLM code review and PR summarization."""

import json

from pydantic import BaseModel

from reviewbot.llm.schemas import PRSummary, ReviewResult

PROMPT_VERSION = "v1"

REVIEW_SYSTEM_PROMPT = """You are a senior software engineer performing a code review
on a GitHub pull request.
Review ONLY the lines that were added or modified (marked with '+' in the diff).
Report only issues you are confident about, with concrete evidence from the code.
Focus on: correctness bugs, security vulnerabilities, error handling, performance
problems, and significant maintainability issues. Do NOT comment on trivial style,
formatting, or personal preference. Do NOT invent issues. If there is nothing
significant, return an empty findings list.
Return ONLY valid JSON matching the provided schema. No markdown, no prose."""

REVIEW_USER_TEMPLATE = """PR title: {title}
PR description: {description}
Language: {language}
File: {path}

Surrounding context (unchanged code, for reference only):
{context}

Diff (line numbers refer to the NEW file):
{numbered_diff}

Schema:
{json_schema}
"""

SUMMARY_SYSTEM_PROMPT_VI = """Bạn là kỹ sư phần mềm cao cấp chịu trách nhiệm tóm tắt
Pull Request trên GitHub.
Nhiệm vụ của bạn là phân tích tiêu đề, mô tả và các thay đổi trong PR để đưa ra:
1. Gợi ý tiêu đề PR chuẩn mực (nếu tiêu đề hiện tại chưa rõ ràng).
2. Tóm tắt ngắn gọn mục tiêu của PR.
3. Danh sách các thay đổi kỹ thuật chính (changes).
4. Các rủi ro tiềm ẩn hoặc tác động phụ cần lưu ý (risks).
5. Các gợi ý kịch bản kiểm thử (test_suggestions).
Ngôn ngữ phản hồi: Tiếng Việt.
Chỉ trả về JSON hợp lệ theo đúng schema được cung cấp. Không bọc văn bản ngoài JSON."""

SUMMARY_SYSTEM_PROMPT_EN = """You are a senior software engineer summarizing a GitHub Pull Request.
Analyze the PR metadata and code changes to provide:
1. A clear, concise title suggestion.
2. A high-level summary of the PR's purpose.
3. Key technical changes introduced.
4. Potential risks, edge cases, or breaking impacts.
5. Actionable test suggestions.
Output language: English.
Return ONLY valid JSON matching the provided schema. No markdown prose outside JSON."""

SUMMARY_USER_TEMPLATE = """PR title: {title}
PR description: {description}

Overview of modified files and changes:
{diff_overview}

Schema:
{json_schema}
"""

RETRY_USER_TEMPLATE = """Your previous response failed JSON validation.
Error message:
{error_message}

Your previous invalid output:
{invalid_output}

Please fix the error and output ONLY valid JSON matching the schema below:
{json_schema}
"""


def build_review_user_prompt(
    title: str,
    description: str,
    language: str,
    path: str,
    numbered_diff: str,
    context: str = "N/A",
) -> str:
    """Construct the formatted user prompt for reviewing a code diff chunk."""
    schema_str = json.dumps(ReviewResult.model_json_schema(), indent=2)
    return REVIEW_USER_TEMPLATE.format(
        title=title or "Untitled PR",
        description=description or "No description provided",
        language=language or "Auto-detect",
        path=path,
        context=context or "No additional context",
        numbered_diff=numbered_diff,
        json_schema=schema_str,
    )


def build_summary_user_prompt(
    title: str,
    description: str,
    diff_overview: str,
) -> str:
    """Construct user prompt for generating a PR summary."""
    schema_str = json.dumps(PRSummary.model_json_schema(), indent=2)
    return SUMMARY_USER_TEMPLATE.format(
        title=title or "Untitled PR",
        description=description or "No description provided",
        diff_overview=diff_overview,
        json_schema=schema_str,
    )


def build_retry_user_prompt(
    error_message: str,
    invalid_output: str,
    target_schema: type[BaseModel],
) -> str:
    """Construct prompt requesting the LLM to fix invalid JSON output."""
    schema_str = json.dumps(target_schema.model_json_schema(), indent=2)
    return RETRY_USER_TEMPLATE.format(
        error_message=error_message,
        invalid_output=invalid_output,
        json_schema=schema_str,
    )
