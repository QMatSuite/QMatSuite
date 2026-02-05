"""
Gate test for Law P3: No Provenance-Dependent Skip Logic.

Per PROVENANCE_VERSIONED_HISTORY_SPEC.md Law P3:
> Skip/rerun decisions MUST NOT consult provenance data.

The manifest.py file (used for incremental run skip logic) MUST NOT
import from the provenance module. Skip logic uses only:
- kind
- pseudo_set_sha
- structure_sha
- step_sha
- done flag

This test uses AST inspection to ensure no provenance imports exist.
"""

import ast
from pathlib import Path

import pytest


def test_manifest_no_provenance_imports():
    """
    Law P3: manifest.py must not import from provenance module.

    Skip logic is for runtime optimization based on SSOT data.
    Provenance is for audit/rollback/analytics only.
    """
    manifest_path = Path(__file__).parents[2] / "src" / "quantumvitas" / "calculation" / "manifest.py"

    if not manifest_path.exists():
        pytest.skip(f"manifest.py not found at {manifest_path}")

    tree = ast.parse(manifest_path.read_text())

    violations = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "provenance" in alias.name.lower():
                    violations.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module and "provenance" in node.module.lower():
                violations.append(f"from {node.module} import ...")

    if violations:
        pytest.fail(
            f"Law P3 violation: manifest.py imports provenance module.\n"
            f"Violations: {violations}\n"
            f"Skip logic must not depend on provenance data."
        )


def test_skip_logic_no_provenance_calls():
    """
    Law P3: Skip decision functions must not call provenance APIs.

    Specifically checks for any function that looks like it's querying
    provenance data (query_operations, query_runs, open_provenance_db, etc.)
    """
    manifest_path = Path(__file__).parents[2] / "src" / "quantumvitas" / "calculation" / "manifest.py"

    if not manifest_path.exists():
        pytest.skip(f"manifest.py not found at {manifest_path}")

    content = manifest_path.read_text()

    # These function names should never appear in manifest.py
    banned_calls = [
        "query_operations",
        "query_runs",
        "get_run_steps",
        "open_provenance_db",
        "ProvenanceDB",
    ]

    violations = []
    for call in banned_calls:
        if call in content:
            violations.append(call)

    if violations:
        pytest.fail(
            f"Law P3 violation: manifest.py contains provenance calls.\n"
            f"Found: {violations}\n"
            f"Skip logic must not depend on provenance data."
        )
