"""
Gate: Daemon Shim Contains No Business Logic

The file `qmatsuite/frontends/daemon/server.py` must be a pure shim that
only re-exports from `qmatsuite.daemon.server`. It must NOT contain:
- Class definitions (class Foo:)
- Function definitions (def foo():)
- Business logic of any kind

This prevents the historical divergence where two daemon implementations
existed in parallel and drifted out of sync.

Canonical implementation: qmatsuite.daemon.server
"""

import ast
from pathlib import Path

import pytest


def _find_repo_root() -> Path:
    """Find repository root (directory containing pyproject.toml or .git)."""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "pyproject.toml").exists() or (current / ".git").exists():
            return current
        current = current.parent
    raise RuntimeError("Could not find repository root")


REPO_ROOT = _find_repo_root()
SHIM_PATH = REPO_ROOT / "src/qmatsuite/frontends/daemon/server.py"
MAX_LINES = 60  # A pure shim should be very short


def test_daemon_shim_is_pure_reexport():
    """Ensure frontends/daemon/server.py is a pure re-export shim."""
    if not SHIM_PATH.exists():
        pytest.skip("Shim file not found (may have been removed)")

    content = SHIM_PATH.read_text()
    lines = content.splitlines()

    # Check line count - a pure shim should be short
    assert len(lines) <= MAX_LINES, (
        f"frontends/daemon/server.py has {len(lines)} lines (max {MAX_LINES}). "
        f"This file must be a pure re-export shim with no business logic. "
        f"The canonical implementation lives in qmatsuite.daemon.server."
    )

    # Parse AST and check for forbidden constructs
    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        pytest.fail(f"Shim has syntax error: {e}")

    forbidden_classes = []
    forbidden_functions = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            forbidden_classes.append(node.name)
        elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            forbidden_functions.append(node.name)

    errors = []
    if forbidden_classes:
        errors.append(f"Contains class definitions: {forbidden_classes}")
    if forbidden_functions:
        errors.append(f"Contains function definitions: {forbidden_functions}")

    if errors:
        pytest.fail(
            f"frontends/daemon/server.py must be a pure re-export shim.\n"
            f"Found forbidden constructs:\n  - " + "\n  - ".join(errors) + "\n"
            f"The canonical implementation lives in qmatsuite.daemon.server.\n"
            f"Do not add logic to the shim."
        )


def test_daemon_shim_has_deprecation_warning():
    """Ensure the shim emits a deprecation warning."""
    if not SHIM_PATH.exists():
        pytest.skip("Shim file not found")

    content = SHIM_PATH.read_text()

    assert "DeprecationWarning" in content, (
        "frontends/daemon/server.py must emit a DeprecationWarning "
        "directing users to import from qmatsuite.daemon.server instead."
    )
    assert "warnings.warn" in content, (
        "frontends/daemon/server.py must use warnings.warn() to emit deprecation."
    )
