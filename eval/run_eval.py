"""Benchmark & Evaluation Engine for ReviewBot.

Measures Precision, Recall, F1-Score, Latency, and Estimated Cost across
labeled test diffs containing security vulnerabilities, runtime bugs, and clean controls.
"""

import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass
from typing import Any

# Ensure src is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from reviewbot.core.linter import CodeLinter

logger = logging.getLogger("reviewbot.eval")

DATASET_CASES: list[dict[str, Any]] = [
    {
        "id": "SEC-01",
        "title": "SQL Injection via f-string",
        "filename": "auth_service.py",
        "patch": (
            "@@ -1,5 +1,6 @@\n"
            " def authenticate_user(cursor, username, password):\n"
            "-    return None\n"
            "+    query = f\"SELECT * FROM users WHERE username = '{username}'\"\n"
            "+    return cursor.execute(query)\n"
        ),
        "expected": [{"category": "security", "severity": "critical", "line": 2}],
    },
    {
        "id": "SEC-02",
        "title": "Arbitrary Code Execution via eval",
        "filename": "formula_evaluator.py",
        "patch": (
            "@@ -1,4 +1,5 @@\n"
            " def parse_and_run(expr):\n"
            "-    return 0\n"
            "+    # Dynamic calculation\n"
            "+    return eval(expr)\n"
        ),
        "expected": [{"category": "security", "severity": "critical", "line": 3}],
    },
    {
        "id": "BUG-03",
        "title": "Division by Zero in Ratio Calculation",
        "filename": "analytics.py",
        "patch": (
            "@@ -1,4 +1,5 @@\n"
            " def compute_ratio(total, count):\n"
            "-    return 0\n"
            "+    ratio = total / 0\n"
            "+    return ratio\n"
        ),
        "expected": [{"category": "bug", "severity": "critical", "line": 2}],
    },
    {
        "id": "SEC-04",
        "title": "Hardcoded API Secret Token",
        "filename": "config.py",
        "patch": (
            '@@ -1,3 +1,4 @@\n import os\n+api_key = "ghp_1234567890abcdefghijklmnopqrstuv"\n'
        ),
        "expected": [{"category": "security", "severity": "critical", "line": 2}],
    },
    {
        "id": "BUG-05",
        "title": "Bare Exception Clause Masking Errors",
        "filename": "worker.py",
        "patch": (
            "@@ -1,4 +1,6 @@\n"
            " def sync_data():\n"
            "-    pass\n"
            "+    try:\n"
            "+        sync()\n"
            "+    except:\n"
            "+        pass\n"
        ),
        "expected": [{"category": "bug", "severity": "minor", "line": 4}],
    },
    {
        "id": "CTRL-06",
        "title": "Clean Math Utility (Control)",
        "filename": "math_utils.py",
        "patch": (
            "@@ -1,4 +1,5 @@\n"
            " def safe_add(a: int, b: int) -> int:\n"
            "-    return 0\n"
            '+    """Return the sum of two integers safely."""\n'
            "+    return a + b\n"
        ),
        "expected": [],
    },
    {
        "id": "CTRL-07",
        "title": "Clean Pydantic Data Model (Control)",
        "filename": "models.py",
        "patch": (
            "@@ -1,4 +1,6 @@\n"
            " from pydantic import BaseModel, Field\n"
            "+class UserDTO(BaseModel):\n"
            "+    username: str = Field(min_length=3)\n"
            "+    email: str\n"
        ),
        "expected": [],
    },
    {
        "id": "CTRL-08",
        "title": "Clean Database Query (Control)",
        "filename": "repository.py",
        "patch": (
            "@@ -1,4 +1,6 @@\n"
            " async def fetch_user(session, user_id: int):\n"
            "-    return None\n"
            "+    stmt = select(User).where(User.id == user_id)\n"
            "+    return await session.scalar(stmt)\n"
        ),
        "expected": [],
    },
    {
        "id": "SEC-09",
        "title": "Command Injection via os.system",
        "filename": "backup.py",
        "patch": (
            "@@ -1,4 +1,5 @@\n"
            " import os\n"
            " def run_archive(folder_path):\n"
            "-    pass\n"
            '+    os.system("tar -czf backup.tar.gz " + folder_path)\n'
        ),
        "expected": [{"category": "security", "severity": "major", "line": 3}],
    },
    {
        "id": "CTRL-10",
        "title": "Clean FastAPI Route (Control)",
        "filename": "router.py",
        "patch": (
            "@@ -1,4 +1,6 @@\n"
            " from fastapi import APIRouter\n"
            " router = APIRouter()\n"
            "+@router.get('/health')\n"
            "+def health_check():\n"
            "+    return {'status': 'healthy'}\n"
        ),
        "expected": [],
    },
]


@dataclass
class CaseResult:
    """Individual test case evaluation output."""

    case_id: str
    title: str
    filename: str
    true_positives: int
    false_positives: int
    false_negatives: int
    findings_detected: int
    duration_ms: int
    passed: bool


@dataclass
class BenchmarkReport:
    """Consolidated benchmark metrics across all test cases."""

    total_cases: int
    vulnerable_cases: int
    control_cases: int
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1_score: float
    avg_latency_ms: float
    total_latency_ms: float
    cost_usd: float
    cases: list[dict[str, Any]]


class BenchmarkEngine:
    """Executes evaluation dataset against ReviewBot static & LLM review components."""

    def __init__(self, dataset_dir: str | None = None) -> None:
        self.dataset_dir = dataset_dir or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "dataset"
        )
        self.linter = CodeLinter()

    def ensure_dataset_files(self) -> None:
        """Persist dataset JSON files if they don't exist."""
        os.makedirs(self.dataset_dir, exist_ok=True)
        for case in DATASET_CASES:
            path = os.path.join(self.dataset_dir, f"{case['id']}.json")
            if not os.path.exists(path):
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(case, f, indent=2)

    def run(self) -> BenchmarkReport:
        """Run evaluation benchmark across all test cases."""
        self.ensure_dataset_files()

        tp_total = 0
        fp_total = 0
        fn_total = 0
        total_time_ms = 0
        case_results: list[dict[str, Any]] = []

        for case in DATASET_CASES:
            start_t = time.perf_counter()
            findings = self.linter.lint_file_diff(case["filename"], case["patch"])
            elapsed_ms = int((time.perf_counter() - start_t) * 1000)
            total_time_ms += elapsed_ms

            expected = case["expected"]
            matched_expected = set()
            unmatched_findings = list(findings)

            # Match detected findings against expected ground truth
            for idx, exp in enumerate(expected):
                for f in findings:
                    if f.category == exp["category"] and abs(f.line - exp["line"]) <= 2:
                        matched_expected.add(idx)
                        if f in unmatched_findings:
                            unmatched_findings.remove(f)

            tp = len(matched_expected)
            fn = len(expected) - tp
            fp = len(unmatched_findings)

            tp_total += tp
            fp_total += fp
            fn_total += fn

            is_passed = (fn == 0) and (fp == 0)

            case_res = CaseResult(
                case_id=case["id"],
                title=case["title"],
                filename=case["filename"],
                true_positives=tp,
                false_positives=fp,
                false_negatives=fn,
                findings_detected=len(findings),
                duration_ms=elapsed_ms,
                passed=is_passed,
            )
            case_results.append(asdict(case_res))

        precision = round(tp_total / (tp_total + fp_total), 4) if (tp_total + fp_total) > 0 else 1.0
        recall = round(tp_total / (tp_total + fn_total), 4) if (tp_total + fn_total) > 0 else 1.0
        f1 = (
            round(2 * (precision * recall) / (precision + recall), 4)
            if (precision + recall) > 0
            else 0.0
        )

        avg_latency = round(total_time_ms / len(DATASET_CASES), 2)

        report = BenchmarkReport(
            total_cases=len(DATASET_CASES),
            vulnerable_cases=sum(1 for c in DATASET_CASES if c["expected"]),
            control_cases=sum(1 for c in DATASET_CASES if not c["expected"]),
            true_positives=tp_total,
            false_positives=fp_total,
            false_negatives=fn_total,
            precision=precision,
            recall=recall,
            f1_score=f1,
            avg_latency_ms=avg_latency,
            total_latency_ms=total_time_ms,
            cost_usd=0.0,
            cases=case_results,
        )

        # Save to eval/results.json
        res_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results.json")
        with open(res_path, "w", encoding="utf-8") as out_fp:
            json.dump(asdict(report), out_fp, indent=2)

        return report

    def format_markdown_table(self, report: BenchmarkReport) -> str:
        """Format benchmark report as a Markdown summary table for thesis report."""
        lines = [
            "# 📊 ReviewBot Evaluation & Benchmark Report",
            "",
            "| Metric | Value | Target Benchmark |",
            "| :--- | :--- | :--- |",
            f"| **Precision** | `{report.precision * 100:.1f}%` | ≥ 85.0% |",
            f"| **Recall** | `{report.recall * 100:.1f}%` | ≥ 90.0% |",
            f"| **F1-Score** | `{report.f1_score * 100:.1f}%` | ≥ 87.0% |",
            f"| **Avg Latency** | `{report.avg_latency_ms:.1f} ms` | < 1000 ms |",
            f"| **Vulnerable Test Diffs** | `{report.vulnerable_cases}` | 6 cases |",
            f"| **Clean Control Diffs** | `{report.control_cases}` | 4 cases |",
            f"| **True Positives (TP)** | `{report.true_positives}` | - |",
            f"| **False Positives (FP)** | `{report.false_positives}` | 0 |",
            f"| **False Negatives (FN)** | `{report.false_negatives}` | 0 |",
            "",
            "### Detailed Case Results",
            "",
            "| Case ID | Title | File | TP | FP | FN | Latency | Status |",
            "| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |",
        ]
        for c in report.cases:
            status_icon = "✅ PASS" if c["passed"] else "❌ FAIL"
            lines.append(
                f"| `{c['case_id']}` | {c['title']} | `{c['filename']}` | "
                f"{c['true_positives']} | {c['false_positives']} | {c['false_negatives']} | "
                f"{c['duration_ms']}ms | {status_icon} |"
            )
        return "\n".join(lines)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    engine = BenchmarkEngine()
    rep = engine.run()
    print(engine.format_markdown_table(rep))
