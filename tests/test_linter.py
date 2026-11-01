"""Unit tests for CodeLinter and PythonASTVisitor."""

from reviewbot.core.linter import CodeLinter


def test_linter_detects_dangerous_eval() -> None:
    code = """def run_user_input(code_str):
    result = eval(code_str)
    return result
"""
    linter = CodeLinter()
    findings = linter.lint_source("runner.py", code)
    assert len(findings) == 1
    assert findings[0].category == "security"
    assert findings[0].severity == "critical"
    assert "eval()" in findings[0].message
    assert findings[0].line == 2


def test_linter_detects_sql_injection() -> None:
    code = """def get_user(cursor, user_id):
    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
"""
    linter = CodeLinter()
    findings = linter.lint_source("db_ops.py", code)
    assert any("SQL Injection" in f.message for f in findings)
    assert any(f.severity == "critical" for f in findings)


def test_linter_detects_division_by_zero() -> None:
    code = """def calculate():
    val = 100 / 0
    return val
"""
    linter = CodeLinter()
    findings = linter.lint_source("calc.py", code)
    assert any("Division or modulo by zero" in f.message for f in findings)


def test_linter_detects_bare_except() -> None:
    code = """try:
    do_something()
except:
    pass
"""
    linter = CodeLinter()
    findings = linter.lint_source("handler.py", code)
    assert any("Bare 'except:'" in f.message for f in findings)


def test_linter_detects_hardcoded_secret() -> None:
    code = """AWS_ACCESS_KEY = "AKIA1234567890EXAMPLE"
api_key = "abcdef1234567890abcdef"
"""
    linter = CodeLinter()
    findings = linter.lint_source("config.py", code)
    assert any("hardcoded secret" in f.message.lower() for f in findings)


def test_linter_clean_code_has_no_findings() -> None:
    code = """import logging

logger = logging.getLogger(__name__)

def add(a: int, b: int) -> int:
    return a + b
"""
    linter = CodeLinter()
    findings = linter.lint_source("math.py", code)
    assert len(findings) == 0
