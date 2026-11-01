"""Static AST & Security Linter for Python code changes."""

import ast
import logging
import re

from reviewbot.core.diff_parser import parse_patch
from reviewbot.core.line_mapper import LineMapper
from reviewbot.llm.schemas import Finding

logger = logging.getLogger("reviewbot.core.linter")

DANGEROUS_FUNCTIONS: dict[str, tuple[str, str, str]] = {
    "eval": (
        "critical",
        "security",
        "Direct use of 'eval()' is extremely dangerous and allows arbitrary code execution. "
        "Use ast.literal_eval() or a safe parser instead.",
    ),
    "exec": (
        "critical",
        "security",
        "Direct use of 'exec()' allows dynamic execution of arbitrary code.",
    ),
    "os.system": (
        "major",
        "security",
        "Avoid using 'os.system()'. Use subprocess.run() with arguments passed as a list "
        "and shell=False to prevent command injection.",
    ),
}

SECRET_KEYWORDS_REGEX = re.compile(
    r"(?i)\b(api_key|secret_key|private_key|auth_token|access_token|password|passwd|db_password)\s*=\s*['\"][A-Za-z0-9_\-\.]{8,}['\"]"
)


class PythonASTVisitor(ast.NodeVisitor):
    """AST Visitor detecting security and bug patterns in Python source code."""

    def __init__(
        self,
        filename: str,
        target_lines: set[int] | None = None,
        source_lines: list[str] | None = None,
    ) -> None:
        self.filename = filename
        self.target_lines = target_lines  # Only report findings on lines changed in PR
        self.source_lines = source_lines or []
        self.findings: list[Finding] = []

    def _is_targeted(self, line: int) -> bool:
        if self.target_lines is None:
            return True
        return line in self.target_lines

    def _get_evidence(self, line: int) -> str:
        if 1 <= line <= len(self.source_lines):
            return self.source_lines[line - 1].strip()
        return ""

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        """Detect f-strings containing SQL statements (potential SQL injection)."""
        has_sql = False
        for part in node.values:
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                val_upper = part.value.upper()
                if any(
                    kw in val_upper
                    for kw in (
                        "SELECT ",
                        "INSERT INTO ",
                        "UPDATE ",
                        "DELETE FROM ",
                        "DROP TABLE ",
                        "WHERE ",
                    )
                ):
                    has_sql = True
                    break

        if has_sql and self._is_targeted(node.lineno):
            self.findings.append(
                Finding(
                    file=self.filename,
                    line=node.lineno,
                    severity="critical",
                    category="security",
                    message=(
                        "Potential SQL Injection: Formatted f-string detected in SQL query. "
                        "String interpolation in SQL allows attacker input to escape query "
                        "context. Use parameterized queries with placeholders instead."
                    ),
                    evidence=self._get_evidence(node.lineno) or "f'SELECT ... {var}'",
                    suggestion="cursor.execute('SELECT ... WHERE col = %s', (val,))",
                    confidence=0.96,
                )
            )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Detect dangerous calls like eval, exec, os.system, or SQL format execution."""
        func_name = ""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                func_name = f"{node.func.value.id}.{node.func.attr}"
            else:
                func_name = node.func.attr

        # 1. Dangerous functions check
        if func_name in DANGEROUS_FUNCTIONS and self._is_targeted(node.lineno):
            severity, category, desc = DANGEROUS_FUNCTIONS[func_name]
            self.findings.append(
                Finding(
                    file=self.filename,
                    line=node.lineno,
                    severity=severity,  # type: ignore[arg-type]
                    category=category,  # type: ignore[arg-type]
                    message=f"Dangerous Function Call: {func_name}(). {desc}",
                    evidence=self._get_evidence(node.lineno) or f"{func_name}(...)",
                    suggestion=f"Refactor to avoid calling {func_name}() directly.",
                    confidence=0.98,
                )
            )

        # 2. SQL injection pattern: cursor.execute(f"SELECT ... {var}")
        if (
            func_name in ("execute", "cursor.execute", "db.execute", "session.execute")
            and node.args
            and self._is_targeted(node.lineno)
        ):
            first_arg = node.args[0]
            is_unsafe_sql = False
            # Check if f-string / JoinedStr
            if isinstance(first_arg, ast.JoinedStr):
                is_unsafe_sql = True
            # Check if BinOp % or +
            elif isinstance(first_arg, ast.BinOp) and isinstance(first_arg.op, (ast.Mod, ast.Add)):
                is_unsafe_sql = True
            # Check if .format()
            elif isinstance(first_arg, ast.Call) and isinstance(first_arg.func, ast.Attribute):
                if first_arg.func.attr == "format":
                    is_unsafe_sql = True

            if is_unsafe_sql:
                self.findings.append(
                    Finding(
                        file=self.filename,
                        line=node.lineno,
                        severity="critical",
                        category="security",
                        message=(
                            "Potential SQL Injection Detected: Detected formatted string or "
                            "concatenation inside database query execution. Use parameterized "
                            "queries with query placeholders instead."
                        ),
                        evidence=self._get_evidence(node.lineno) or "execute(...)",
                        suggestion="cursor.execute('SELECT ... WHERE id = %s', (val,))",
                        confidence=0.95,
                    )
                )

        self.generic_visit(node)

    def visit_Try(self, node: ast.Try) -> None:
        """Detect bare except: or except Exception: pass."""
        for handler in node.handlers:
            if handler.type is None:
                # Bare except:
                if self._is_targeted(handler.lineno):
                    self.findings.append(
                        Finding(
                            file=self.filename,
                            line=handler.lineno,
                            severity="minor",
                            category="bug",
                            message=(
                                "Bare 'except:' intercepts KeyboardInterrupt and SystemExit, "
                                "masking fatal errors. Catch specific exceptions like "
                                "'except Exception:' instead."
                            ),
                            evidence=self._get_evidence(handler.lineno) or "except:",
                            suggestion=(
                                "except Exception as exc:\n    logger.error('Failed: %s', exc)"
                            ),
                            confidence=0.9,
                        )
                    )
            elif (
                len(handler.body) == 1
                and isinstance(handler.body[0], ast.Pass)
                and self._is_targeted(handler.lineno)
            ):
                self.findings.append(
                    Finding(
                        file=self.filename,
                        line=handler.lineno,
                        severity="minor",
                        category="bug",
                        message="Silently suppressing exceptions with 'pass' may hide subtle bugs.",
                        evidence=self._get_evidence(handler.lineno) or "pass",
                        suggestion="Log the exception or re-raise if it cannot be handled.",
                        confidence=0.85,
                    )
                )
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> None:
        """Detect division by literal zero."""
        if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)):
            if isinstance(node.right, ast.Constant) and node.right.value == 0:
                if self._is_targeted(node.lineno):
                    self.findings.append(
                        Finding(
                            file=self.filename,
                            line=node.lineno,
                            severity="critical",
                            category="bug",
                            message=(
                                "Division or modulo by zero will raise a ZeroDivisionError "
                                "at runtime."
                            ),
                            evidence=self._get_evidence(node.lineno) or "/ 0",
                            suggestion="Verify denominator is not zero before dividing.",
                            confidence=1.0,
                        )
                    )
        self.generic_visit(node)


class CodeLinter:
    """Multi-language static analyzer combining AST analysis and security heuristics."""

    def lint_source(
        self,
        filename: str,
        content: str,
        target_lines: set[int] | None = None,
    ) -> list[Finding]:
        """Lint a single source file and return findings."""
        findings: list[Finding] = []

        # 1. Regex check for hardcoded secrets on target lines
        lines = content.splitlines()
        for idx, line in enumerate(lines, start=1):
            if target_lines is not None and idx not in target_lines:
                continue
            if SECRET_KEYWORDS_REGEX.search(line):
                findings.append(
                    Finding(
                        file=filename,
                        line=idx,
                        severity="critical",
                        category="security",
                        message=(
                            "Detected potential hardcoded secret or token. Credentials should "
                            "never be checked into version control. "
                            "Use environment variables instead."
                        ),
                        evidence=line.strip(),
                        suggestion="os.environ.get('KEY_NAME')",
                        confidence=0.92,
                    )
                )

        # 2. Python AST analysis if file is python
        if filename.endswith(".py"):
            try:
                tree = ast.parse(content, filename=filename)
                visitor = PythonASTVisitor(
                    filename=filename,
                    target_lines=target_lines,
                    source_lines=lines,
                )
                visitor.visit(tree)
                findings.extend(visitor.findings)
            except SyntaxError as exc:
                logger.debug("Syntax error parsing %s for AST linting: %s", filename, exc)

        return findings

    def lint_file_diff(
        self,
        filename: str,
        patch: str,
        full_content: str | None = None,
    ) -> list[Finding]:
        """Lint changes based on unified diff patch and optional full file content."""
        diff = parse_patch(patch, filename)
        added_lines = LineMapper.get_added_line_numbers(diff)

        if not added_lines:
            return []

        # If full content is not available, reconstruct minimal pseudo-file from patch lines
        if full_content is None:
            lines_dict: dict[int, str] = {}
            for hunk in diff.hunks:
                for diff_line in hunk.lines:
                    if diff_line.type in ("add", "context") and diff_line.new_line_no is not None:
                        lines_dict[diff_line.new_line_no] = diff_line.content

            if not lines_dict:
                return []

            max_line = max(lines_dict.keys())
            # 1-indexed lines: line 1 at index 0
            full_lines = [lines_dict.get(i, "") for i in range(1, max_line + 1)]
            full_content = "\n".join(full_lines)

        return self.lint_source(filename, full_content, target_lines=added_lines)
