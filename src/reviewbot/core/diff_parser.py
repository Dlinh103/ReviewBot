"""Unified diff parser extracting files, hunks, and lines with accurate line numbers."""

import re
from dataclasses import dataclass, field
from typing import Literal

HUNK_HEADER_PATTERN = re.compile(
    r"^@@\s+-(?P<old_start>\d+)(?:,(?P<old_count>\d+))?"
    r"\s+\+(?P<new_start>\d+)(?:,(?P<new_count>\d+))?\s+@@(?: *(?P<heading>.*))?$"
)


@dataclass
class DiffLine:
    """Represents a single line within a diff hunk."""

    type: Literal["add", "del", "context"]
    content: str
    old_line_no: int | None
    new_line_no: int | None
    raw: str


@dataclass
class Hunk:
    """Represents a single diff hunk beginning with @@ ... @@."""

    header: str
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    heading: str = ""
    lines: list[DiffLine] = field(default_factory=list)


@dataclass
class FileDiff:
    """Represents changes in a single file."""

    path: str
    old_path: str | None = None
    status: str = "modified"  # added, modified, deleted, renamed
    hunks: list[Hunk] = field(default_factory=list)
    additions: int = 0
    deletions: int = 0

    @property
    def added_lines(self) -> list[DiffLine]:
        """All lines added in this file diff."""
        res: list[DiffLine] = []
        for hunk in self.hunks:
            for line in hunk.lines:
                if line.type == "add":
                    res.append(line)
        return res


def parse_patch(
    patch_str: str,
    filename: str,
    status: str = "modified",
    old_filename: str | None = None,
) -> FileDiff:
    """Parse unified diff patch text into a structured FileDiff object."""
    file_diff = FileDiff(
        path=filename,
        old_path=old_filename or filename,
        status=status,
    )

    if not patch_str or not patch_str.strip():
        return file_diff

    lines = patch_str.splitlines()
    current_hunk: Hunk | None = None
    old_line = 0
    new_line = 0

    for raw_line in lines:
        match = HUNK_HEADER_PATTERN.match(raw_line)
        if match:
            old_start = int(match.group("old_start"))
            old_count = int(match.group("old_count")) if match.group("old_count") else 1
            new_start = int(match.group("new_start"))
            new_count = int(match.group("new_count")) if match.group("new_count") else 1
            heading = match.group("heading") or ""

            current_hunk = Hunk(
                header=raw_line,
                old_start=old_start,
                old_count=old_count,
                new_start=new_start,
                new_count=new_count,
                heading=heading,
            )
            file_diff.hunks.append(current_hunk)
            old_line = old_start
            new_line = new_start
            continue

        if current_hunk is None:
            # Preamble line before first hunk, skip
            continue

        if raw_line.startswith("+"):
            content = raw_line[1:]
            diff_line = DiffLine(
                type="add",
                content=content,
                old_line_no=None,
                new_line_no=new_line,
                raw=raw_line,
            )
            current_hunk.lines.append(diff_line)
            file_diff.additions += 1
            new_line += 1

        elif raw_line.startswith("-"):
            content = raw_line[1:]
            diff_line = DiffLine(
                type="del",
                content=content,
                old_line_no=old_line,
                new_line_no=None,
                raw=raw_line,
            )
            current_hunk.lines.append(diff_line)
            file_diff.deletions += 1
            old_line += 1

        elif raw_line.startswith(" ") or raw_line == "":
            content = raw_line[1:] if raw_line.startswith(" ") else ""
            diff_line = DiffLine(
                type="context",
                content=content,
                old_line_no=old_line,
                new_line_no=new_line,
                raw=raw_line,
            )
            current_hunk.lines.append(diff_line)
            old_line += 1
            new_line += 1

        elif raw_line.startswith(r"\ No newline at end of file"):
            # Informational line; does not increment line numbers
            continue

    return file_diff
