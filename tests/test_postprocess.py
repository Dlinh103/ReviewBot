"""Unit tests for PostProcessor and comment formatting."""

from reviewbot.core.diff_parser import parse_patch
from reviewbot.core.postprocess import PostProcessor, format_inline_comment
from reviewbot.llm.schemas import Finding

SAMPLE_DIFF = """@@ -10,5 +10,6 @@
 int a = 1;
-int b = 2;
+int b = 3;
+int c = 4;
 int d = 5;
"""


def test_format_inline_comment_with_suggestion() -> None:
    finding = Finding(
        file="main.c",
        line=11,
        severity="critical",
        category="security",
        message="Buffer overflow detected",
        evidence="char buf[10];",
        suggestion="char buf[64];",
        confidence=0.9,
    )
    formatted = format_inline_comment(finding)
    assert "🔴 **[CRITICAL]**" in formatted
    assert "🛡️ Security" in formatted
    assert "Buffer overflow detected" in formatted
    assert "char buf[10];" in formatted
    assert "```suggestion\nchar buf[64];\n```" in formatted
    assert "Confidence: 90%" in formatted


def test_format_inline_comment_without_suggestion() -> None:
    finding = Finding(
        file="main.c",
        line=11,
        severity="minor",
        category="style",
        message="Variable name too short",
        evidence="int b = 3;",
        suggestion=None,
        confidence=0.7,
    )
    formatted = format_inline_comment(finding)
    assert "🟡 **[MINOR]**" in formatted
    assert "🎨 Style" in formatted
    assert "```suggestion" not in formatted


def test_postprocess_confidence_filter() -> None:
    file_diff = parse_patch(SAMPLE_DIFF, "main.c")
    diffs_map = {"main.c": file_diff}

    f_high = Finding(
        file="main.c", line=11, severity="major", category="bug",
        message="Valid bug", evidence="b = 3;", confidence=0.8,
    )
    f_low = Finding(
        file="main.c", line=12, severity="minor", category="style",
        message="Low confidence", evidence="c = 4;", confidence=0.4,
    )

    processor = PostProcessor(min_confidence=0.6)
    results = processor.process_findings([f_high, f_low], diffs_map)

    assert len(results) == 1
    assert results[0].message == "Valid bug"


def test_postprocess_line_filter_and_snap() -> None:
    file_diff = parse_patch(SAMPLE_DIFF, "main.c")
    diffs_map = {"main.c": file_diff}

    # Line 11 is on added line ('+int b = 3;') -> kept at 11
    f_exact = Finding(
        file="main.c", line=11, severity="major", category="bug",
        message="Exact line", evidence="b = 3;", confidence=0.8,
    )
    # Line 10 is on context line ('int a = 1;') -> snapped to nearest added line 11
    f_context = Finding(
        file="main.c", line=10, severity="major", category="performance",
        message="Context line snap", evidence="a = 1;", confidence=0.8,
    )
    # Line 999 is completely outside diff -> discarded
    f_outside = Finding(
        file="main.c", line=999, severity="critical", category="bug",
        message="Far line", evidence="x = 1;", confidence=0.99,
    )

    processor = PostProcessor(min_confidence=0.5)
    results = processor.process_findings([f_exact, f_context, f_outside], diffs_map)

    assert len(results) == 2
    assert results[0].line == 11
    assert results[1].line == 11


def test_postprocess_deduplication() -> None:
    file_diff = parse_patch(SAMPLE_DIFF, "main.c")
    diffs_map = {"main.c": file_diff}

    # Two findings on the same file, line, and category
    f1 = Finding(
        file="main.c", line=11, severity="minor", category="bug",
        message="Duplicate 1", evidence="b = 3;", confidence=0.7,
    )
    f2 = Finding(
        file="main.c", line=11, severity="critical", category="bug",
        message="Duplicate 2 higher severity", evidence="b = 3;", confidence=0.9,
    )

    processor = PostProcessor()
    results = processor.process_findings([f1, f2], diffs_map)

    assert len(results) == 1
    # Should keep higher severity finding
    assert results[0].severity == "critical"
    assert results[0].confidence == 0.9


def test_postprocess_ranking_and_capping() -> None:
    file_diff = parse_patch(SAMPLE_DIFF, "main.c")
    diffs_map = {"main.c": file_diff}

    # Create 5 findings: severity info, minor, major, critical
    findings = [
        Finding(
            file="main.c", line=11, severity="info", category="maintainability",
            message="info", evidence=".", confidence=0.9,
        ),
        Finding(
            file="main.c", line=11, severity="minor", category="style",
            message="minor", evidence=".", confidence=0.8,
        ),
        Finding(
            file="main.c", line=12, severity="critical", category="security",
            message="critical", evidence=".", confidence=0.7,
        ),
        Finding(
            file="main.c", line=12, severity="major", category="bug",
            message="major", evidence=".", confidence=0.95,
        ),
    ]

    processor = PostProcessor(max_comments=2)
    results = processor.process_findings(findings, diffs_map)

    # Capped at 2 comments, ranked by severity
    assert len(results) == 2
    assert results[0].severity == "critical"
    assert results[1].severity == "major"
