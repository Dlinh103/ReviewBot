"""Unit tests for unified diff parser."""

from pathlib import Path

from reviewbot.core.diff_parser import parse_patch

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_parse_added_file() -> None:
    patch_text = (FIXTURES_DIR / "added_file.diff").read_text(encoding="utf-8")
    diff = parse_patch(patch_text, "src/greeting.py", status="added")

    assert diff.path == "src/greeting.py"
    assert diff.status == "added"
    assert len(diff.hunks) == 1
    assert diff.additions == 7
    assert diff.deletions == 0

    hunk = diff.hunks[0]
    assert hunk.new_start == 1
    assert hunk.new_count == 7
    assert len(hunk.lines) == 7

    for idx, line in enumerate(hunk.lines, start=1):
        assert line.type == "add"
        assert line.new_line_no == idx
        assert line.old_line_no is None


def test_parse_modified_file_multiple_hunks() -> None:
    patch_text = (FIXTURES_DIR / "modified_python.diff").read_text(encoding="utf-8")
    diff = parse_patch(patch_text, "app/calc.py", status="modified")

    assert len(diff.hunks) == 2
    assert diff.additions == 3
    assert diff.deletions == 2

    # Hunk 1
    h1 = diff.hunks[0]
    assert h1.old_start == 10
    assert h1.new_start == 10

    # Line 1: context line "    total = 0" -> new_line_no = 10, old_line_no = 10
    assert h1.lines[0].type == "context"
    assert h1.lines[0].old_line_no == 10
    assert h1.lines[0].new_line_no == 10

    # Line 3: deleted line "-        total += item.price" -> old_line_no = 12, new_line_no = None
    del_line = [item for item in h1.lines if item.type == "del"][0]
    assert del_line.old_line_no == 12
    assert del_line.new_line_no is None

    # Line 4: added line "+        if item.is_valid:" -> old_line_no = None, new_line_no = 12
    add_lines = [item for item in h1.lines if item.type == "add"]
    assert add_lines[0].new_line_no == 12
    assert add_lines[1].new_line_no == 13

    # Hunk 2
    h2 = diff.hunks[1]
    assert h2.old_start == 35
    assert h2.new_start == 37


def test_parse_deleted_file() -> None:
    patch_text = (FIXTURES_DIR / "deleted_file.diff").read_text(encoding="utf-8")
    diff = parse_patch(patch_text, "old/code.py", status="deleted")

    assert diff.status == "deleted"
    assert diff.additions == 0
    assert diff.deletions == 4
    for line in diff.hunks[0].lines:
        assert line.type == "del"
        assert line.new_line_no is None
        assert line.old_line_no is not None


def test_parse_renamed_file() -> None:
    patch_text = (FIXTURES_DIR / "renamed_file.diff").read_text(encoding="utf-8")
    diff = parse_patch(
        patch_text,
        "new/app.py",
        status="renamed",
        old_filename="old/app.py",
    )

    assert diff.path == "new/app.py"
    assert diff.old_path == "old/app.py"
    assert diff.additions == 1
    assert diff.deletions == 1


def test_parse_empty_patch() -> None:
    diff = parse_patch("", "empty.py")
    assert len(diff.hunks) == 0
    assert diff.additions == 0
    assert diff.deletions == 0


def test_parse_hunk_without_counts() -> None:
    patch = "@@ -1 +1 @@\n-old\n+new\n"
    diff = parse_patch(patch, "single.txt")
    assert len(diff.hunks) == 1
    hunk = diff.hunks[0]
    assert hunk.old_start == 1
    assert hunk.old_count == 1
    assert hunk.new_start == 1
    assert hunk.new_count == 1
    assert diff.additions == 1
    assert diff.deletions == 1
