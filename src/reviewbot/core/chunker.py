"""Split diffs into token-budgeted chunks with numbered lines for LLM consumption."""

import math
from dataclasses import dataclass

from reviewbot.core.diff_parser import FileDiff, Hunk


@dataclass
class DiffChunk:
    """A self-contained slice of diff suitable for sending to an LLM."""

    file_path: str
    numbered_diff: str
    start_line: int
    end_line: int
    estimated_tokens: int
    hunks: list[Hunk]


def estimate_tokens(text: str) -> int:
    """Heuristic token estimation: ~4 characters per token."""
    if not text:
        return 0
    return max(1, math.ceil(len(text) / 4))


def format_numbered_hunk(hunk: Hunk) -> str:
    """Format a hunk with explicit new line numbers on every line.

    Example:
        @@ -10,3 +10,4 @@
         L10:   const a = 1;
        +L11: + const b = 2;
         L12:   return a + b;
    """
    out: list[str] = [hunk.header]
    for line in hunk.lines:
        if line.type == "add":
            line_str = f"+L{line.new_line_no}: +{line.content}"
        elif line.type == "del":
            line_str = f"-    : -{line.content}"
        else:
            line_str = f" L{line.new_line_no}:  {line.content}"
        out.append(line_str)
    return "\n".join(out)


class DiffChunker:
    """Splits FileDiff objects into token-bounded DiffChunks."""

    def __init__(self, max_tokens_per_chunk: int = 6000) -> None:
        self.max_tokens_per_chunk = max_tokens_per_chunk

    def chunk_file_diff(self, file_diff: FileDiff) -> list[DiffChunk]:
        """Split a single file diff into one or more chunks."""
        if not file_diff.hunks:
            return []

        chunks: list[DiffChunk] = []
        current_hunks: list[Hunk] = []
        current_formatted: list[str] = []
        current_tokens = 0
        current_start = file_diff.hunks[0].new_start

        for hunk in file_diff.hunks:
            formatted_hunk = format_numbered_hunk(hunk)
            hunk_tokens = estimate_tokens(formatted_hunk)

            # If adding this hunk exceeds budget and we already have hunks accumulated
            if current_hunks and (current_tokens + hunk_tokens > self.max_tokens_per_chunk):
                numbered_text = "\n\n".join(current_formatted)
                hunk_last = current_hunks[-1]
                end_line = hunk_last.new_start + max(hunk_last.new_count, 1) - 1

                chunks.append(
                    DiffChunk(
                        file_path=file_diff.path,
                        numbered_diff=numbered_text,
                        start_line=current_start,
                        end_line=end_line,
                        estimated_tokens=current_tokens,
                        hunks=list(current_hunks),
                    )
                )
                current_hunks = []
                current_formatted = []
                current_tokens = 0
                current_start = hunk.new_start

            current_hunks.append(hunk)
            current_formatted.append(formatted_hunk)
            current_tokens += hunk_tokens

        # Flush remaining hunks
        if current_hunks:
            numbered_text = "\n\n".join(current_formatted)
            hunk_last = current_hunks[-1]
            end_line = hunk_last.new_start + max(hunk_last.new_count, 1) - 1

            chunks.append(
                DiffChunk(
                    file_path=file_diff.path,
                    numbered_diff=numbered_text,
                    start_line=current_start,
                    end_line=end_line,
                    estimated_tokens=current_tokens,
                    hunks=current_hunks,
                )
            )

        return chunks

    def chunk_all(self, file_diffs: list[FileDiff]) -> list[DiffChunk]:
        """Split a list of file diffs into chunks."""
        all_chunks: list[DiffChunk] = []
        for file_diff in file_diffs:
            all_chunks.extend(self.chunk_file_diff(file_diff))
        return all_chunks
