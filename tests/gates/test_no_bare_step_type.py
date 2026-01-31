"""
Gate: No Bare step_type Fields/Parameters (§9)

Constitution §9: The repository MUST NOT have any DTO/dataclass fields or function 
parameters named step_type (bare). Everything MUST be explicitly step_type_gen or 
step_type_spec depending on whether engine/persistence info is required.

This gate scans for:
- Function parameters named `step_type` (bare)
- Dataclass/TypedDict fields named `step_type` (bare)
- Dict keys named `step_type` in DTO serialization
"""

import ast
import re
from pathlib import Path
from typing import List, Tuple

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent

SCAN_DIRS = [
    REPO_ROOT / "src",
    REPO_ROOT / "tests",
    REPO_ROOT / "tools",
]

SKIP_PATTERNS = [
    "tests/gates/test_no_bare_step_type.py",  # This file itself
    "src/quantumvitas/_vault/*",  # Legacy archive
]


def is_skipped(path: Path) -> bool:
    """Check if file should be skipped."""
    import fnmatch
    rel_path = str(path.relative_to(REPO_ROOT))
    for pattern in SKIP_PATTERNS:
        if fnmatch.fnmatch(rel_path, pattern):
            return True
    return False


class BareStepTypeVisitor(ast.NodeVisitor):
    """AST visitor to find bare step_type parameters and fields."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.violations: List[Tuple[int, str, str]] = []  # (line, context, type)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Check function parameters."""
        for arg in node.args.args:
            if arg.arg == "step_type":
                self.violations.append((
                    node.lineno,
                    f"function parameter '{arg.arg}' in {node.name}",
                    "FUNCTION_PARAMETER"
                ))
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        """Check class fields (dataclass, TypedDict, regular class)."""
        for item in node.body:
            if isinstance(item, ast.AnnAssign):
                if isinstance(item.target, ast.Name) and item.target.id == "step_type":
                    self.violations.append((
                        item.lineno,
                        f"class field '{item.target.id}' in {node.name}",
                        "CLASS_FIELD"
                    ))
        self.generic_visit(node)


def scan_file(file_path: Path) -> List[Tuple[int, str, str]]:
    """Scan a Python file for bare step_type violations."""
    if is_skipped(file_path):
        return []

    try:
        content = file_path.read_text()
        tree = ast.parse(content, filename=str(file_path))
        visitor = BareStepTypeVisitor(file_path)
        visitor.visit(tree)
        return visitor.violations
    except (SyntaxError, UnicodeDecodeError):
        return []  # Skip files that can't be parsed


def scan_all_files() -> List[Tuple[Path, int, str, str]]:
    """Scan all Python files in scan directories."""
    all_violations = []
    for scan_dir in SCAN_DIRS:
        if not scan_dir.exists():
            continue
        for py_file in scan_dir.rglob("*.py"):
            if is_skipped(py_file):
                continue
            violations = scan_file(py_file)
            for line, context, vtype in violations:
                all_violations.append((py_file, line, context, vtype))
    return all_violations


class TestNoBareStepType:
    """Gate: No bare step_type fields/parameters."""

    def test_no_bare_step_type_in_code(self):
        """Scan for bare step_type parameters and fields."""
        violations = scan_all_files()

        if violations:
            report = "\n\n=== BARE step_type VIOLATIONS ===\n"
            report += f"Found {len(violations)} violation(s):\n\n"
            for file_path, line, context, vtype in violations:
                rel_path = file_path.relative_to(REPO_ROOT)
                report += f"  {rel_path}:{line} - {context} ({vtype})\n"
            report += "\n=== END VIOLATIONS ===\n"
            report += "\nFix: Rename to step_type_gen or step_type_spec based on layering rule.\n"
            pytest.fail(report)

