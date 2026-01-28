"""
Gate 0.1: Multiple QVService Definition Detector

Ensures only one QVService class exists in production code.
Only src/quantumvitas/api/service.py may define class QVService.
"""

import ast
from pathlib import Path


def test_single_qvservice_definition():
    """Ensure only one QVService class exists in production code."""
    # Use absolute path from repo root
    repo_root = Path(__file__).parent.parent.parent
    src = repo_root / "src" / "quantumvitas"
    definitions = []

    for py_file in src.rglob("*.py"):
        # Skip vault directory and test files
        if "_vault" in str(py_file) or "test_" in py_file.name:
            continue

        try:
            content = py_file.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == "QVService":
                    rel_path = py_file.relative_to(repo_root / "src")
                    definitions.append((str(rel_path), node.lineno))
        except (SyntaxError, UnicodeDecodeError):
            # Skip files that can't be parsed
            continue

    # Only api/service.py should define QVService
    canonical_path = "quantumvitas/api/service.py"
    violations = []
    allowed = None

    for file_path, line_no in definitions:
        # Check if this is the canonical path (file_path is relative to src/)
        if file_path == canonical_path or "api/service.py" in file_path:
            allowed = f"{file_path}:{line_no} (ALLOWED - canonical)"
        else:
            violations.append(f"{file_path}:{line_no} (VIOLATION)")

    if violations:
        error_msg = "ERROR: Multiple QVService definitions found:\n"
        if allowed:
            error_msg += f"  - {allowed}\n"
        for violation in violations:
            error_msg += f"  - {violation}\n"
        error_msg += f"\nOnly {canonical_path} may define class QVService."
        assert False, error_msg

    # Ensure canonical definition exists
    if not definitions:
        assert False, f"No QVService definitions found. Expected one in {canonical_path}"
    assert allowed is not None, f"Canonical QVService definition not found in {canonical_path}. Found: {definitions}"

