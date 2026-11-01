"""Unit tests for LineMapper."""

from reviewbot.core.diff_parser import parse_patch
from reviewbot.core.line_mapper import LineMapper

SAMPLE_DIFF = """@@ -10,5 +10,6 @@
 int a = 1;
-int b = 2;
+int b = 3;
+int c = 4;
 int d = 5;
"""


def test_get_added_line_numbers() -> None:
    file_diff = parse_patch(SAMPLE_DIFF, "main.c")
    added = LineMapper.get_added_line_numbers(file_diff)
    # Line 10 is context ('int a = 1;')
    # Line 11 is add ('int b = 3;')
    # Line 12 is add ('int c = 4;')
    # Line 13 is context ('int d = 5;')
    assert added == {11, 12}


def test_is_line_in_diff() -> None:
    file_diff = parse_patch(SAMPLE_DIFF, "main.c")
    assert LineMapper.is_line_in_diff(11, file_diff) is True
    assert LineMapper.is_line_in_diff(12, file_diff) is True
    # Line 10 is context: false without allow_context, true with allow_context
    assert LineMapper.is_line_in_diff(10, file_diff, allow_context=False) is False
    assert LineMapper.is_line_in_diff(10, file_diff, allow_context=True) is True
    # Line 99 is completely outside diff
    assert LineMapper.is_line_in_diff(99, file_diff, allow_context=True) is False


def test_find_nearest_add_line() -> None:
    file_diff = parse_patch(SAMPLE_DIFF, "main.c")
    # Proposed line 10 (context line) -> nearest added line is 11 (distance 1)
    nearest = LineMapper.find_nearest_add_line(10, file_diff, max_distance=2)
    assert nearest == 11

    # Proposed line 13 -> nearest is 12 (distance 1)
    nearest2 = LineMapper.find_nearest_add_line(13, file_diff, max_distance=2)
    assert nearest2 == 12

    # Proposed line 20 -> outside max_distance=2
    nearest_far = LineMapper.find_nearest_add_line(20, file_diff, max_distance=2)
    assert nearest_far is None


def test_get_hunk_for_line() -> None:
    file_diff = parse_patch(SAMPLE_DIFF, "main.c")
    hunk = LineMapper.get_hunk_for_line(11, file_diff)
    assert hunk is not None
    assert hunk.new_start == 10

    hunk_none = LineMapper.get_hunk_for_line(99, file_diff)
    assert hunk_none is None
