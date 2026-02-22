"""
Gate B: Forbid service-delegating utils wrappers.

Per API Constitution Law H2.2:
- Utils functions MUST NOT contain get_service() or QMSService()
- Utils functions MUST NOT be thin forwarders to service methods

Rationale: These wrappers were removed during API slimming.
           Re-adding them is drift that inflates the API surface.
"""

import ast
from pathlib import Path

import pytest


UTILS_PATH = Path(__file__).parent.parent.parent / "src" / "qmatsuite" / "api" / "utils.py"


class ServiceDelegationVisitor(ast.NodeVisitor):
    """AST visitor to detect service delegation patterns in function bodies."""

    def __init__(self):
        self.violations = []
        self.current_function = None

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        # Skip private/internal functions
        if node.name.startswith("_"):
            self.generic_visit(node)
            return

        self.current_function = node.name

        # Check for service delegation patterns in the function body
        has_get_service = False
        has_qmsservice = False

        for child in ast.walk(node):
            # Check for get_service(...) calls
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name) and child.func.id == "get_service":
                    has_get_service = True
                elif isinstance(child.func, ast.Attribute) and child.func.attr == "get_service":
                    has_get_service = True

            # Check for QMSService(...) instantiation
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name) and child.func.id == "QMSService":
                    has_qmsservice = True
                elif isinstance(child.func, ast.Attribute) and child.func.attr == "QMSService":
                    has_qmsservice = True

        if has_get_service or has_qmsservice:
            self.violations.append({
                "function": node.name,
                "line": node.lineno,
                "has_get_service": has_get_service,
                "has_qmsservice": has_qmsservice,
            })

        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        # Treat async functions the same as regular functions
        self.visit_FunctionDef(node)  # type: ignore


def find_service_delegating_wrappers() -> list[dict]:
    """
    Scan utils.py for functions that delegate to service methods.

    Returns:
        List of violation dicts with function name, line number, and pattern found.
    """
    if not UTILS_PATH.exists():
        return []

    source = UTILS_PATH.read_text()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    visitor = ServiceDelegationVisitor()
    visitor.visit(tree)

    return visitor.violations


class TestNoServiceDelegatingUtils:
    """Gate B: Utils must not contain service-delegating wrappers."""

    def test_no_get_service_in_utils(self):
        """
        Utils functions must not call get_service().

        Per Law H2.2, SERVICE_DELEGATION is a forbidden pattern in utils.
        If you need to call a service method, call it directly at the call site,
        not via a utils wrapper.
        """
        violations = find_service_delegating_wrappers()

        if violations:
            violation_report = "\n".join(
                f"  Line {v['line']}: {v['function']}() - "
                f"{'get_service()' if v['has_get_service'] else ''}"
                f"{' + ' if v['has_get_service'] and v['has_qmsservice'] else ''}"
                f"{'QMSService()' if v['has_qmsservice'] else ''}"
                for v in violations
            )
            pytest.fail(
                f"Found {len(violations)} service-delegating wrapper(s) in utils.py:\n"
                f"{violation_report}\n\n"
                f"Per Law H2.2, these are SERVICE_DELEGATION violations.\n"
                f"Remedy: Remove the wrapper and call the service method directly at the call site."
            )

    def test_utils_file_exists(self):
        """Verify utils.py exists (sanity check)."""
        assert UTILS_PATH.exists(), f"utils.py not found at {UTILS_PATH}"
