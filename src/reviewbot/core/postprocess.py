"""Post-processing pipeline for LLM review findings.

Includes filtering, deduplication, ranking, and formatting.
"""

import logging

from reviewbot.core.diff_parser import FileDiff
from reviewbot.core.line_mapper import LineMapper
from reviewbot.llm.schemas import Finding

logger = logging.getLogger("reviewbot.core.postprocess")

SEVERITY_ORDER = {
    "critical": 4,
    "major": 3,
    "minor": 2,
    "info": 1,
}

SEVERITY_BADGES = {
    "critical": "🔴 **[CRITICAL]**",
    "major": "🟠 **[MAJOR]**",
    "minor": "🟡 **[MINOR]**",
    "info": "🔵 **[INFO]**",
}

CATEGORY_ICONS = {
    "bug": "🐛 Bug",
    "security": "🛡️ Security",
    "performance": "⚡ Performance",
    "maintainability": "🔧 Maintainability",
    "style": "🎨 Style",
    "test": "🧪 Test",
}


def format_inline_comment(finding: Finding) -> str:
    """Format a finding into GitHub Markdown inline comment with optional suggestion."""
    sev_badge = SEVERITY_BADGES.get(finding.severity, f"**[{finding.severity.upper()}]**")
    cat_label = CATEGORY_ICONS.get(finding.category, finding.category.capitalize())

    lines: list[str] = [
        f"{sev_badge} {cat_label}",
        "",
        finding.message,
    ]

    if finding.evidence and finding.evidence.strip():
        lines.extend(
            [
                "",
                "> **Evidence:**",
                f"> `{finding.evidence.strip()}`",
            ]
        )

    if finding.suggestion and finding.suggestion.strip():
        # Clean potential markdown fences within suggestion text
        raw_sugg = finding.suggestion.strip()
        if raw_sugg.startswith("```"):
            clean_sugg = "\n".join([ln for ln in raw_sugg.splitlines() if not ln.startswith("```")])
        else:
            clean_sugg = raw_sugg

        lines.extend(
            [
                "",
                "```suggestion",
                clean_sugg,
                "```",
            ]
        )

    lines.append(f"\n*Confidence: {int(finding.confidence * 100)}%*")
    return "\n".join(lines)


class PostProcessor:
    """Filters, deduplicates, and ranks review findings before publishing to GitHub."""

    def __init__(
        self,
        min_confidence: float = 0.6,
        max_comments: int = 15,
    ) -> None:
        self.min_confidence = min_confidence
        self.max_comments = max_comments

    def process_findings(
        self,
        findings: list[Finding],
        file_diffs_map: dict[str, FileDiff],
        min_confidence: float | None = None,
        max_comments: int | None = None,
    ) -> list[Finding]:
        """Apply all post-processing rules to raw LLM findings."""
        target_min_confidence = (
            min_confidence if min_confidence is not None else self.min_confidence
        )
        target_max_comments = max_comments if max_comments is not None else self.max_comments

        # 1. Filter by confidence threshold
        confident: list[Finding] = [f for f in findings if f.confidence >= target_min_confidence]
        logger.info(
            "Confidence filter (>= %.2f): %d/%d findings passed",
            target_min_confidence,
            len(confident),
            len(findings),
        )

        # 2. Filter by line validity within diff (and snap to nearest added line if close)
        valid_in_diff: list[Finding] = []
        for f in confident:
            file_diff = file_diffs_map.get(f.file)
            if not file_diff:
                logger.warning("Finding discarded: file '%s' not in diff", f.file)
                continue

            if LineMapper.is_line_in_diff(f.line, file_diff):
                valid_in_diff.append(f)
            else:
                # Attempt to snap to nearest added line within max_distance=2
                nearest = LineMapper.find_nearest_add_line(f.line, file_diff, max_distance=2)
                if nearest is not None:
                    logger.debug(
                        "Snapped finding from line %d to nearest added line %d in %s",
                        f.line,
                        nearest,
                        f.file,
                    )
                    f.line = nearest
                    valid_in_diff.append(f)
                else:
                    logger.warning(
                        "Finding discarded: line %d not on added line in %s",
                        f.line,
                        f.file,
                    )

        # 3. Deduplication by (file, line, category)
        deduped_map: dict[tuple[str, int, str], Finding] = {}
        for f in valid_in_diff:
            key = (f.file, f.line, f.category)
            if key not in deduped_map:
                deduped_map[key] = f
            else:
                # Keep finding with higher confidence or higher severity
                existing = deduped_map[key]
                existing_weight = SEVERITY_ORDER.get(existing.severity, 0)
                new_weight = SEVERITY_ORDER.get(f.severity, 0)
                if (new_weight > existing_weight) or (
                    new_weight == existing_weight and f.confidence > existing.confidence
                ):
                    deduped_map[key] = f

        deduped = list(deduped_map.values())
        logger.info("Deduplication: %d findings remaining", len(deduped))

        # 4. Ranking: Severity (critical -> info) then Confidence (high -> low)
        ranked = sorted(
            deduped,
            key=lambda x: (SEVERITY_ORDER.get(x.severity, 0), x.confidence),
            reverse=True,
        )

        # 5. Cap maximum comments per PR
        capped = ranked[:target_max_comments]
        if len(ranked) > target_max_comments:
            logger.info("Capped comments from %d to %d", len(ranked), target_max_comments)

        return capped
