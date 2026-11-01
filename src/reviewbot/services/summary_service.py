"""Service for generating and publishing Pull Request summaries."""

import logging
from typing import Any

from reviewbot.config import Settings, get_settings
from reviewbot.github.client import GitHubClient
from reviewbot.llm.base import LLMClient, LLMResponse
from reviewbot.llm.reviewer import summarize_pr
from reviewbot.llm.schemas import PRSummary

logger = logging.getLogger("reviewbot.services.summary")


def format_pr_summary_markdown(summary: PRSummary, language: str = "vi") -> str:
    """Format PRSummary object into structured GitHub issue comment markdown."""
    lines: list[str] = [
        GitHubClient.SUMMARY_MARKER,
        "## 🤖 ReviewBot Pull Request Summary",
        "",
    ]

    if language.lower() == "vi":
        lines.extend([
            f"**💡 Gợi ý tiêu đề PR:** `{summary.title_suggestion}`",
            "",
            "### 📌 Tóm tắt (Summary)",
            summary.summary,
            "",
            "### 🛠️ Thay đổi chính (Key Changes)",
        ])
        for change in summary.changes:
            lines.append(f"- {change}")

        lines.extend([
            "",
            "### ⚠️ Rủi ro tiềm ẩn (Risks & Considerations)",
        ])
        for risk in summary.risks:
            lines.append(f"- {risk}")

        lines.extend([
            "",
            "### 🧪 Gợi ý kiểm thử (Test Suggestions)",
        ])
        for test in summary.test_suggestions:
            lines.append(f"- {test}")

    else:
        lines.extend([
            f"**💡 Suggested Title:** `{summary.title_suggestion}`",
            "",
            "### 📌 Summary",
            summary.summary,
            "",
            "### 🛠️ Key Changes",
        ])
        for change in summary.changes:
            lines.append(f"- {change}")

        lines.extend([
            "",
            "### ⚠️ Risks & Considerations",
        ])
        for risk in summary.risks:
            lines.append(f"- {risk}")

        lines.extend([
            "",
            "### 🧪 Test Suggestions",
        ])
        for test in summary.test_suggestions:
            lines.append(f"- {test}")

    lines.append("\n---\n*Generated automatically by ReviewBot*")
    return "\n".join(lines)


class SummaryService:
    """Orchestrates PR summarization and comment upserting."""

    def __init__(
        self,
        llm_client: LLMClient,
        settings: Settings | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.settings = settings or get_settings()

    async def generate_and_post_summary(
        self,
        github_client: GitHubClient,
        repo_full_name: str,
        pr_number: int,
        pr_title: str,
        pr_description: str,
        diff_overview: str,
        language: str | None = None,
    ) -> tuple[PRSummary, LLMResponse, dict[str, Any]]:
        """Generate PR summary via LLM and upsert comment on GitHub."""
        target_lang = language or self.settings.OUTPUT_LANGUAGE
        logger.info(
            "Generating PR summary for %s#%s in language '%s'",
            repo_full_name,
            pr_number,
            target_lang,
        )
        summary, telemetry = await summarize_pr(
            llm_client=self.llm_client,
            pr_title=pr_title,
            pr_description=pr_description,
            diff_overview=diff_overview,
            output_language=target_lang,
        )

        comment_markdown = format_pr_summary_markdown(
            summary,
            language=target_lang,
        )

        comment_res = await github_client.upsert_issue_comment(
            repo_full_name=repo_full_name,
            pr_number=pr_number,
            body=comment_markdown,
            marker=GitHubClient.SUMMARY_MARKER,
        )

        return summary, telemetry, comment_res
