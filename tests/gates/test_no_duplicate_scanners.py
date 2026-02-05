"""
Gate test for Law P9: Single Artifact Scanner (No Duplicate Logic).

Per PROVENANCE_VERSIONED_HISTORY_SPEC.md Law P9:
> Artifact scanning MUST occur only at Runner level.
> No duplicate scanners in handlers or engines.

This test uses AST inspection to ensure handlers and engine modules
do not import or implement their own artifact scanning.
"""

import ast
from pathlib import Path

import pytest


def test_handler_no_scanner_import():
    """
    Law P9: Handler files must not import artifact scanner.

    Artifact scanning is Runner's responsibility. Handlers dispatch
    to engines but do not track what files were created/modified.
    """
    drivers_dir = Path(__file__).parents[2] / "src" / "quantumvitas" / "drivers"

    if not drivers_dir.exists():
        pytest.skip(f"Drivers directory not found at {drivers_dir}")

    handler_files = list(drivers_dir.rglob("handler.py"))

    if not handler_files:
        pytest.skip("No handler.py files found")

    violations = []

    for handler_path in handler_files:
        tree = ast.parse(handler_path.read_text())

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and "scanner" in node.module.lower():
                    rel_path = handler_path.relative_to(drivers_dir.parent)
                    violations.append(f"{rel_path}: from {node.module}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if "scanner" in alias.name.lower():
                        rel_path = handler_path.relative_to(drivers_dir.parent)
                        violations.append(f"{rel_path}: import {alias.name}")

    if violations:
        pytest.fail(
            f"Law P9 violation: Handler(s) import scanner module.\n"
            f"Violations:\n" + "\n".join(f"  - {v}" for v in violations) + "\n"
            f"Artifact scanning must only occur at Runner level."
        )


def test_engine_no_scanner_import():
    """
    Law P9: Engine modules must not import artifact scanner.

    Engine code generates input files and runs executables.
    It should not track artifacts - that's Runner's job.
    """
    drivers_dir = Path(__file__).parents[2] / "src" / "quantumvitas" / "drivers"

    if not drivers_dir.exists():
        pytest.skip(f"Drivers directory not found at {drivers_dir}")

    # Check driver.py and recipe.py files (not handler.py, covered above)
    engine_files = []
    engine_files.extend(drivers_dir.rglob("driver.py"))
    engine_files.extend(drivers_dir.rglob("recipe.py"))

    if not engine_files:
        pytest.skip("No driver.py or recipe.py files found")

    violations = []

    for engine_path in engine_files:
        try:
            tree = ast.parse(engine_path.read_text())
        except SyntaxError:
            continue  # Skip files with syntax errors

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                # Allow importing ArtifactPolicy (for defining policy constants)
                # but not ArtifactScanner (which does the actual scanning)
                if node.module and "scanner" in node.module.lower():
                    for alias in node.names:
                        if alias.name == "ArtifactScanner":
                            rel_path = engine_path.relative_to(drivers_dir.parent)
                            violations.append(f"{rel_path}: from {node.module} import ArtifactScanner")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if "scanner" in alias.name.lower():
                        rel_path = engine_path.relative_to(drivers_dir.parent)
                        violations.append(f"{rel_path}: import {alias.name}")

    if violations:
        pytest.fail(
            f"Law P9 violation: Engine module(s) import ArtifactScanner.\n"
            f"Violations:\n" + "\n".join(f"  - {v}" for v in violations) + "\n"
            f"Engines may import ArtifactPolicy (to define constants) but not ArtifactScanner.\n"
            f"Artifact scanning must only occur at Runner level."
        )


def test_no_duplicate_scanner_implementations():
    """
    Law P9: No duplicate scanner implementations outside provenance module.

    Checks that no other file defines a class that looks like an artifact scanner.
    """
    src_dir = Path(__file__).parents[2] / "src" / "quantumvitas"

    if not src_dir.exists():
        pytest.skip(f"Source directory not found at {src_dir}")

    # Files that ARE allowed to define scanner classes
    allowed_files = {
        "provenance/scanner.py",
    }

    violations = []

    for py_file in src_dir.rglob("*.py"):
        rel_path = str(py_file.relative_to(src_dir))

        if rel_path in allowed_files:
            continue

        try:
            tree = ast.parse(py_file.read_text())
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check for class names that suggest artifact scanning
                name_lower = node.name.lower()
                if "artifactscanner" in name_lower or "filescanner" in name_lower:
                    violations.append(f"{rel_path}: class {node.name}")

    if violations:
        pytest.fail(
            f"Law P9 violation: Duplicate scanner implementations found.\n"
            f"Violations:\n" + "\n".join(f"  - {v}" for v in violations) + "\n"
            f"There should be exactly one ArtifactScanner in provenance/scanner.py."
        )
