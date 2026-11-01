"""Filter files that should not be reviewed (lock files, binaries, minified code, vendor)."""

import logging
from fnmatch import fnmatch
from typing import Any

logger = logging.getLogger("reviewbot.core.file_filter")

DEFAULT_IGNORE_PATTERNS = [
    # Package lock files
    "*.lock",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "Cargo.lock",
    "poetry.lock",
    "Pipfile.lock",
    "composer.lock",
    "packages.lock.json",
    # Minified and compiled bundles
    "*.min.js",
    "*.min.css",
    "*.map",
    "*.bundle.js",
    "dist/**",
    "build/**",
    "out/**",
    ".next/**",
    # Binaries and assets
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.svg",
    "*.ico",
    "*.pdf",
    "*.zip",
    "*.tar",
    "*.gz",
    "*.woff",
    "*.woff2",
    "*.ttf",
    "*.eot",
    "*.exe",
    "*.bin",
    "*.pyd",
    "*.pyc",
    "*.class",
    "*.jar",
    # Vendor and third-party directories
    "node_modules/**",
    "vendor/**",
    "vendors/**",
    "third_party/**",
    # Generated / documentation
    "*.generated.*",
    "coverage/**",
    ".coverage*",
    "__pycache__/**",
]


class FileFilter:
    """Evaluates whether files in a PR should be included in LLM code review."""

    def __init__(
        self,
        ignore_patterns: list[str] | None = None,
        max_changes_per_file: int = 1500,
    ) -> None:
        self.ignore_patterns = (
            ignore_patterns if ignore_patterns is not None else DEFAULT_IGNORE_PATTERNS
        )
        self.max_changes_per_file = max_changes_per_file

    def is_ignored(
        self,
        path: str,
        status: str = "modified",
        changes: int = 0,
        patch: str | None = None,
        extra_ignore_patterns: list[str] | None = None,
    ) -> tuple[bool, str]:
        """Check if a single file should be ignored."""
        normalized_path = path.replace("\\", "/").lstrip("/")

        # 1. Ignored statuses (deleted files have no new code to comment on)
        if status.lower() == "deleted":
            return True, "File deleted"

        # 2. Binary files have no text patch
        if patch is None or status.lower() == "binary":
            return True, "Binary or missing patch"

        # 3. Check pattern matches
        all_patterns = self.ignore_patterns + (extra_ignore_patterns or [])
        for pattern in all_patterns:
            pattern_norm = pattern.replace("\\", "/").lstrip("/")
            if fnmatch(normalized_path, pattern_norm):
                return True, f"Matched ignore pattern '{pattern}'"
            # Also test basename
            basename = normalized_path.split("/")[-1]
            if fnmatch(basename, pattern_norm):
                return True, f"Matched ignore pattern '{pattern}'"

        # 4. Check file size / lines changed threshold
        if changes > self.max_changes_per_file:
            return True, f"File diff too large ({changes} lines > {self.max_changes_per_file})"

        return False, ""

    def filter_files(
        self,
        files: list[dict[str, Any]],
        max_files: int = 40,
        extra_ignore_patterns: list[str] | None = None,
    ) -> tuple[list[dict[str, Any]], list[tuple[str, str]]]:
        """Filter a list of GitHub file objects.

        Returns:
            (retained_files, skipped_files_with_reasons)
        """
        retained: list[dict[str, Any]] = []
        skipped: list[tuple[str, str]] = []

        for f in files:
            filename = f.get("filename", "")
            status = f.get("status", "modified")
            changes = f.get("changes", 0)
            patch = f.get("patch")

            ignored, reason = self.is_ignored(
                filename,
                status=status,
                changes=changes,
                patch=patch,
                extra_ignore_patterns=extra_ignore_patterns,
            )
            if ignored:
                skipped.append((filename, reason))
                logger.info("Skipping file '%s': %s", filename, reason)
            else:
                retained.append(f)

        # Enforce max files cap
        if len(retained) > max_files:
            overflow = retained[max_files:]
            retained = retained[:max_files]
            for f in overflow:
                filename = f.get("filename", "")
                reason = f"Exceeded MAX_FILES_PER_PR cap ({max_files})"
                skipped.append((filename, reason))
                logger.warning("Capped file '%s': %s", filename, reason)

        return retained, skipped
