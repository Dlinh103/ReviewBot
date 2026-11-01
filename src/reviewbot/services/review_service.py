"""Main orchestration service executing the end-to-end PR review pipeline."""

import asyncio
import logging
import time
from typing import Any

from reviewbot.config import Settings, get_settings
from reviewbot.core.chunker import DiffChunk, DiffChunker
from reviewbot.core.config_loader import RepoConfig, parse_repo_config
from reviewbot.core.diff_parser import FileDiff, parse_patch
from reviewbot.core.file_filter import FileFilter
from reviewbot.core.linter import CodeLinter
from reviewbot.core.postprocess import PostProcessor, format_inline_comment
from reviewbot.core.secrets_scrubber import scrub_secrets
from reviewbot.github.client import GitHubClient
from reviewbot.llm.base import LLMClient
from reviewbot.llm.reviewer import review_chunk
from reviewbot.llm.schemas import Finding
from reviewbot.services.summary_service import SummaryService

logger = logging.getLogger("reviewbot.services.review")


class ReviewService:
    """Orchestrates pulling diffs, analyzing with LLM, and publishing GitHub reviews."""

    def __init__(
        self,
        llm_client: LLMClient,
        settings: Settings | None = None,
        max_concurrency: int = 3,
    ) -> None:
        self.llm_client = llm_client
        self.settings = settings or get_settings()
        self.max_concurrency = max_concurrency
        self.file_filter = FileFilter()
        self.linter = CodeLinter()
        self.chunker = DiffChunker(max_tokens_per_chunk=self.settings.MAX_DIFF_TOKENS_PER_CHUNK)
        self.postprocessor = PostProcessor(
            min_confidence=self.settings.MIN_CONFIDENCE,
            max_comments=self.settings.MAX_COMMENTS_PER_PR,
        )
        self.summary_service = SummaryService(llm_client=self.llm_client, settings=self.settings)

    async def review_pull_request(
        self,
        github_client: GitHubClient,
        repo_full_name: str,
        pr_number: int,
        head_sha: str,
        pr_title: str = "",
        pr_body: str = "",
    ) -> dict[str, Any]:
        """Execute full review pipeline for a pull request."""
        start_time = time.perf_counter()
        logger.info(
            "Starting review pipeline for %s#%s (head: %s)",
            repo_full_name, pr_number, head_sha,
        )

        # 0. Load repository custom config (.reviewbot.yml) if available
        repo_config = RepoConfig()
        for cfg_name in [".reviewbot.yml", ".reviewbot.yaml", ".github/.reviewbot.yml"]:
            try:
                cfg_content = await github_client.get_file_content(
                    repo_full_name, cfg_name, ref=head_sha
                )
                if cfg_content:
                    repo_config = parse_repo_config(cfg_content)
                    logger.info("Loaded custom .reviewbot config from %s", cfg_name)
                    break
            except Exception as exc:
                logger.debug("Config check failed for %s: %s", cfg_name, exc)

        # 1. Fetch changed files from GitHub
        raw_files = await github_client.get_pr_files(repo_full_name, pr_number)

        # 2. Filter files (ignore lock files, binaries, custom ignore rules, capped at MAX_FILES)
        retained_files, skipped_files = self.file_filter.filter_files(
            raw_files,
            max_files=self.settings.MAX_FILES_PER_PR,
            extra_ignore_patterns=repo_config.ignore,
        )
        logger.info(
            "File filtering: %d retained, %d skipped for %s#%s",
            len(retained_files),
            len(skipped_files),
            repo_full_name,
            pr_number,
        )

        # 3. Parse patches, run static AST linter, scrub secrets, and collect diff chunks
        file_diffs_map: dict[str, FileDiff] = {}
        all_chunks: list[DiffChunk] = []
        diff_overview_lines: list[str] = []
        all_findings: list[Finding] = []

        for f in retained_files:
            filename = f.get("filename", "")
            status = f.get("status", "modified")
            raw_patch = f.get("patch", "")

            # Run deterministic static AST & security linter
            if raw_patch:
                static_findings = self.linter.lint_file_diff(filename, raw_patch)
                if static_findings:
                    logger.info(
                        "Linter detected %d finding(s) in %s",
                        len(static_findings),
                        filename,
                    )
                    all_findings.extend(static_findings)

            # Scrub secrets before any LLM chunking
            clean_patch, redactions = scrub_secrets(raw_patch)
            if redactions > 0:
                logger.info("Redacted %d secret(s) in %s", redactions, filename)

            file_diff = parse_patch(clean_patch, filename, status=status)
            file_diffs_map[filename] = file_diff

            chunks = self.chunker.chunk_file_diff(file_diff)
            all_chunks.extend(chunks)

            diff_overview_lines.append(
                f"- `{filename}` ({status}): +{file_diff.additions}, -{file_diff.deletions}"
            )

        # 4. Review chunks in parallel with concurrency semaphore
        semaphore = asyncio.Semaphore(self.max_concurrency)
        total_input_tokens = 0
        total_output_tokens = 0
        total_cost_usd = 0.0

        async def process_chunk(chunk: DiffChunk) -> list[Finding]:
            nonlocal total_input_tokens, total_output_tokens, total_cost_usd
            async with semaphore:
                res, tele = await review_chunk(
                    llm_client=self.llm_client,
                    chunk=chunk,
                    pr_title=pr_title,
                    pr_description=pr_body,
                )
                total_input_tokens += tele.input_tokens
                total_output_tokens += tele.output_tokens
                total_cost_usd += tele.estimated_cost_usd
                return res.findings

        if all_chunks:
            chunk_results = await asyncio.gather(
                *(process_chunk(chunk) for chunk in all_chunks),
                return_exceptions=False,
            )
            for findings in chunk_results:
                all_findings.extend(findings)

        logger.info(
            "Raw findings collected: %d (LLM + static linter) across %d chunks",
            len(all_findings), len(all_chunks),
        )

        # 5. Post-process findings (confidence, diff validity, deduplication, ranking, capping)
        final_findings = self.postprocessor.process_findings(
            all_findings,
            file_diffs_map,
            min_confidence=repo_config.min_confidence,
            max_comments=repo_config.max_comments,
        )
        logger.info("Final findings to publish: %d", len(final_findings))

        # 6. Format and submit GitHub Review with inline comments
        inline_comments = [
            {
                "path": f.file,
                "line": f.line,
                "side": "RIGHT",
                "body": format_inline_comment(f),
            }
            for f in final_findings
        ]

        # Construct review body summary
        crit_count = sum(1 for f in final_findings if f.severity == "critical")
        maj_count = sum(1 for f in final_findings if f.severity == "major")
        min_count = sum(1 for f in final_findings if f.severity == "minor")
        info_count = sum(1 for f in final_findings if f.severity == "info")

        if final_findings:
            review_body = (
                f"## 🤖 ReviewBot Automated Code Review\n\n"
                f"Found **{len(final_findings)}** issue(s) across {len(retained_files)} file(s):\n"
                f"- 🔴 Critical: {crit_count}\n"
                f"- 🟠 Major: {maj_count}\n"
                f"- 🟡 Minor: {min_count}\n"
                f"- 🔵 Info: {info_count}\n\n"
                f"*Please review the inline comments below.*"
            )
        else:
            review_body = (
                "## 🤖 ReviewBot Automated Code Review\n\n"
                f"✅ **No significant issues found.** All {len(retained_files)} "
                "reviewed file(s) look good!"
            )

        review_res = await github_client.create_review(
            repo_full_name=repo_full_name,
            pr_number=pr_number,
            commit_id=head_sha,
            body=review_body,
            comments=inline_comments,
            event="COMMENT",
        )

        # 7. Generate and post high-level PR summary
        diff_overview_text = (
            "\n".join(diff_overview_lines) if diff_overview_lines else "No code changes."
        )
        summary, sum_tele, comment_res = await self.summary_service.generate_and_post_summary(
            github_client=github_client,
            repo_full_name=repo_full_name,
            pr_number=pr_number,
            pr_title=pr_title,
            pr_description=pr_body,
            diff_overview=diff_overview_text,
            language=repo_config.language,
        )

        total_input_tokens += sum_tele.input_tokens
        total_output_tokens += sum_tele.output_tokens
        total_cost_usd += sum_tele.estimated_cost_usd
        duration_ms = int((time.perf_counter() - start_time) * 1000)

        logger.info(
            "Review pipeline completed for %s#%s in %dms [cost=$%.4f]",
            repo_full_name,
            pr_number,
            duration_ms,
            total_cost_usd,
        )

        return {
            "status": "done",
            "repo": repo_full_name,
            "pr_number": pr_number,
            "head_sha": head_sha,
            "findings_count": len(final_findings),
            "findings": [f.model_dump() for f in final_findings],
            "summary": summary.model_dump(),
            "github_review_id": review_res.get("id"),
            "summary_comment_id": comment_res.get("id"),
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "total_cost_usd": round(total_cost_usd, 6),
            "duration_ms": duration_ms,
        }
