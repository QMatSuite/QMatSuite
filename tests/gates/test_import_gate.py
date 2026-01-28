"""
Import gate test: Enforce API-only imports for CLI and Daemon.

This test ensures that CLI and Daemon do not bypass the domain API by directly
importing kernel modules (core, workflow, history, etc.).

Mission:
- CLI and Daemon MUST only import from quantumvitas.api and quantumvitas.api.utils
- No kernel bypass imports allowed
- LegacyService must remain ZERO
"""

import ast
from pathlib import Path
from typing import List, Tuple


def test_cli_daemon_import_gate():
    """
    Gate test: Enforce that CLI and Daemon only import from quantumvitas.api.

    This prevents kernel bypass and ensures frontends use the domain API.

    Rules:
    - CLI and Daemon MUST NOT import from kernel modules (core, workflow, history, etc.)
    - Only allowed quantumvitas imports: quantumvitas.api.* and quantumvitas.api.utils
    - Relative imports within daemon/cli packages are allowed (they're internal to the package)
    - Third-party and stdlib imports are allowed
    """
    project_root = Path(__file__).parent.parent.parent

    # Directories to scan
    daemon_dir = project_root / "src" / "quantumvitas" / "daemon"
    cli_dir = project_root / "src" / "quantumvitas" / "cli"

    # Collect all Python files
    files_to_check = []
    for directory in [daemon_dir, cli_dir]:
        if directory.exists():
            files_to_check.extend(directory.rglob("*.py"))

    # Allowed quantumvitas import prefixes
    allowed_qv_prefixes = [
        "quantumvitas.api",
        "quantumvitas.api.utils",
    ]

    # Forbidden kernel modules (for error messages)
    forbidden_examples = [
        "quantumvitas.core",
        "quantumvitas.workflow",
        "quantumvitas.history",
        "quantumvitas.analysis",
        "quantumvitas.engine",
        "quantumvitas.calculation",
        "quantumvitas.execution",
        "quantumvitas.io",
        "quantumvitas.drivers",
        "quantumvitas.presets",
        "quantumvitas.project",
        "quantumvitas._api_legacy",
        "quantumvitas.api_legacy",
    ]

    violations = []

    for file_path in files_to_check:
        try:
            content = file_path.read_text()
            tree = ast.parse(content, filename=str(file_path))

            for node in ast.walk(tree):
                imports_to_check = []

                if isinstance(node, ast.Import):
                    # Handle: import x.y.z
                    for alias in node.names:
                        imports_to_check.append((alias.name, node.lineno))

                elif isinstance(node, ast.ImportFrom):
                    # Handle: from x.y import z
                    # Skip relative imports (node.level > 0) - they're internal to daemon/cli
                    if node.module and node.level == 0:
                        imports_to_check.append((node.module, node.lineno))

                for imported_module, lineno in imports_to_check:
                    # Only check quantumvitas.* imports
                    if imported_module.startswith("quantumvitas."):
                        # Must match one of the allowed prefixes
                        allowed = any(
                            imported_module.startswith(prefix)
                            for prefix in allowed_qv_prefixes
                        )
                        if not allowed:
                            violations.append({
                                "file": str(file_path.relative_to(project_root)),
                                "line": lineno,
                                "module": imported_module,
                            })
        except Exception as e:
            # If we can't parse the file, that's a problem
            violations.append({
                "file": str(file_path.relative_to(project_root)),
                "line": 0,
                "module": f"[PARSE ERROR: {e}]",
            })

    if violations:
        error_msg = "\n\n" + "="*80 + "\n"
        error_msg += "IMPORT GATE VIOLATION: CLI/Daemon must only import quantumvitas.api.*\n"
        error_msg += "="*80 + "\n\n"
        error_msg += f"Found {len(violations)} forbidden import(s):\n\n"

        for v in violations:
            error_msg += f"  {v['file']}:{v['line']}\n"
            error_msg += f"    → imports '{v['module']}'\n\n"

        error_msg += "ALLOWED quantumvitas imports:\n"
        for prefix in allowed_qv_prefixes:
            error_msg += f"  ✓ {prefix}\n"
            error_msg += f"  ✓ {prefix}.*\n"
        error_msg += "\n"

        error_msg += "FORBIDDEN kernel imports (examples):\n"
        for module in forbidden_examples[:6]:
            error_msg += f"  ✗ {module}\n"
            error_msg += f"  ✗ {module}.*\n"
        error_msg += "\n"

        error_msg += "FIX: Use the domain API (quantumvitas.api.QVService) instead of kernel imports.\n"
        error_msg += "="*80 + "\n"

        raise AssertionError(error_msg)
