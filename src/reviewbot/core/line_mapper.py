"""Maps line numbers to valid diff positions for GitHub review comments."""

from reviewbot.core.diff_parser import FileDiff, Hunk


class LineMapper:
    """Helper to validate and map line numbers within modified hunks."""

    @staticmethod
    def get_added_line_numbers(file_diff: FileDiff) -> set[int]:
        """Return the set of new file line numbers that were added or modified."""
        added_lines: set[int] = set()
        for hunk in file_diff.hunks:
            for line in hunk.lines:
                if line.type == "add" and line.new_line_no is not None:
                    added_lines.add(line.new_line_no)
        return added_lines

    @staticmethod
    def get_all_diff_line_numbers(file_diff: FileDiff) -> set[int]:
        """Return all new file line numbers present in the diff (added and context)."""
        all_lines: set[int] = set()
        for hunk in file_diff.hunks:
            for line in hunk.lines:
                if line.new_line_no is not None:
                    all_lines.add(line.new_line_no)
        return all_lines

    @classmethod
    def is_line_in_diff(
        cls,
        line_no: int,
        file_diff: FileDiff,
        allow_context: bool = False,
    ) -> bool:
        """Check if a line number is eligible for an inline review comment.

        By default, comments should be placed strictly on added/modified lines ('+').
        """
        valid_lines = (
            cls.get_all_diff_line_numbers(file_diff)
            if allow_context
            else cls.get_added_line_numbers(file_diff)
        )
        return line_no in valid_lines

    @classmethod
    def find_nearest_add_line(
        cls,
        line_no: int,
        file_diff: FileDiff,
        max_distance: int = 2,
    ) -> int | None:
        """Find the closest added line if the proposed line is within a small window.

        Useful when LLM points to a line immediately adjacent to modified code.
        """
        added_lines = cls.get_added_line_numbers(file_diff)
        if not added_lines:
            return None

        if line_no in added_lines:
            return line_no

        closest_line: int | None = None
        min_distance = max_distance + 1

        for candidate in sorted(added_lines):
            distance = abs(candidate - line_no)
            if distance <= max_distance and distance < min_distance:
                min_distance = distance
                closest_line = candidate

        return closest_line

    @staticmethod
    def get_hunk_for_line(line_no: int, file_diff: FileDiff) -> Hunk | None:
        """Find which hunk contains the given new file line number."""
        for hunk in file_diff.hunks:
            hunk_end = hunk.new_start + max(hunk.new_count, 1) - 1
            if hunk.new_start <= line_no <= hunk_end:
                return hunk
        return None
