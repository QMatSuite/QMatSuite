"""
Gate C: Forbid service_nested stub/placeholder methods.

Per API Constitution:
- Service methods MUST NOT be stubs or placeholders
- Exposing half-baked API capabilities is not allowed

Detects:
- `return []`, `return {}`, `return None` with TODO/not implemented comments
- `raise NotImplementedError` or similar
- `pass` only bodies
- "not implemented" error messages
"""

import ast
import re
from pathlib import Path

import pytest


SERVICE_PATH = Path(__file__).parent.parent.parent / "src" / "qmatsuite" / "api" / "service.py"

# Patterns that indicate stub/placeholder implementations
STUB_PATTERNS = [
    r"not\s+implemented",
    r"TODO",
    r"FIXME",
    r"stub",
    r"placeholder",
    r"coming\s+soon",
]


class StubMethodVisitor(ast.NodeVisitor):
    """AST visitor to detect stub/placeholder method patterns."""

    def __init__(self, source_lines: list[str]):
        self.violations = []
        self.source_lines = source_lines
        self.current_class = None

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        # Skip private/internal functions and __init__
        if node.name.startswith("_"):
            return

        # Only check methods inside nested service classes
        if not self.current_class:
            return

        # Skip non-nested classes (QMSService itself)
        if self.current_class == "QMSService":
            return

        violation = self._check_stub_patterns(node)
        if violation:
            self.violations.append(violation)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.visit_FunctionDef(node)  # type: ignore

    def _check_stub_patterns(self, node: ast.FunctionDef) -> dict | None:
        """Check if a method body is a stub/placeholder."""
        body = node.body

        # Filter out docstrings
        actual_body = [
            stmt for stmt in body
            if not (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant))
        ]

        if not actual_body:
            return None

        # Check for single-statement stubs
        if len(actual_body) == 1:
            stmt = actual_body[0]

            # Pattern: pass only
            if isinstance(stmt, ast.Pass):
                return {
                    "class": self.current_class,
                    "method": node.name,
                    "line": node.lineno,
                    "reason": "Method body is only `pass`",
                }

            # Pattern: raise NotImplementedError
            if isinstance(stmt, ast.Raise):
                if isinstance(stmt.exc, ast.Call):
                    func = stmt.exc.func
                    if isinstance(func, ast.Name) and func.id == "NotImplementedError":
                        return {
                            "class": self.current_class,
                            "method": node.name,
                            "line": node.lineno,
                            "reason": "Raises NotImplementedError",
                        }
                elif isinstance(stmt.exc, ast.Name) and stmt.exc.id == "NotImplementedError":
                    return {
                        "class": self.current_class,
                        "method": node.name,
                        "line": node.lineno,
                        "reason": "Raises NotImplementedError",
                    }

            # Pattern: return [], return {}, return None with stub comments
            if isinstance(stmt, ast.Return):
                return_val = stmt.value
                is_empty_return = (
                    return_val is None or
                    (isinstance(return_val, ast.List) and len(return_val.elts) == 0) or
                    (isinstance(return_val, ast.Dict) and len(return_val.keys) == 0) or
                    (isinstance(return_val, ast.Constant) and return_val.value is None)
                )

                if is_empty_return:
                    # Check for stub comments in the method source
                    method_source = self._get_method_source(node)
                    for pattern in STUB_PATTERNS:
                        if re.search(pattern, method_source, re.IGNORECASE):
                            return {
                                "class": self.current_class,
                                "method": node.name,
                                "line": node.lineno,
                                "reason": f"Returns empty value with stub comment matching '{pattern}'",
                            }

        # Check for explicit stub error raises (e.g., raise ValueError("Not implemented"))
        # Note: We only flag raises that are the ONLY statement in the body (besides docstring)
        # If a method has real logic but also raises for some paths, that's legitimate
        if len(actual_body) == 1:
            stmt = actual_body[0]
            if isinstance(stmt, ast.Raise) and stmt.exc:
                # Check if the exception message contains "not implemented"
                if isinstance(stmt.exc, ast.Call) and stmt.exc.args:
                    for arg in stmt.exc.args:
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                            if "not implemented" in arg.value.lower():
                                return {
                                    "class": self.current_class,
                                    "method": node.name,
                                    "line": node.lineno,
                                    "reason": "Raises with 'not implemented' message",
                                }

        return None

    def _get_method_source(self, node: ast.FunctionDef) -> str:
        """Extract the source code for a method."""
        start_line = node.lineno - 1
        end_line = node.end_lineno if node.end_lineno else start_line + 1
        return "\n".join(self.source_lines[start_line:end_line])


def find_stub_service_methods() -> list[dict]:
    """
    Scan service.py for stub/placeholder nested service methods.

    Returns:
        List of violation dicts with class name, method name, line number, and reason.
    """
    if not SERVICE_PATH.exists():
        return []

    source = SERVICE_PATH.read_text()
    source_lines = source.split("\n")

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    visitor = StubMethodVisitor(source_lines)
    visitor.visit(tree)

    return visitor.violations


class TestNoStubServiceMethods:
    """Gate C: Service methods must not be stubs or placeholders."""

    def test_no_stub_nested_service_methods(self):
        """
        Nested service methods must not be stubs or placeholders.

        Don't expose half-baked API capabilities. If a method isn't
        implemented, don't put it in the API at all.
        """
        violations = find_stub_service_methods()

        if violations:
            violation_report = "\n".join(
                f"  Line {v['line']}: {v['class']}.{v['method']}() - {v['reason']}"
                for v in violations
            )
            pytest.fail(
                f"Found {len(violations)} stub/placeholder service method(s):\n"
                f"{violation_report}\n\n"
                f"Don't expose half-baked API capabilities.\n"
                f"Remedy: Either implement the method fully or remove it from the API."
            )

    def test_service_file_exists(self):
        """Verify service.py exists (sanity check)."""
        assert SERVICE_PATH.exists(), f"service.py not found at {SERVICE_PATH}"
