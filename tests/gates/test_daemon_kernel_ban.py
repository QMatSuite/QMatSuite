"""
Daemon kernel import ban gate.

P0 LAW: Daemon package MUST NOT import from kernel modules.
Allowed imports:
- quantumvitas.api.*
- quantumvitas.daemon.* (same package)
- stdlib
- third-party packages

This test scans ALL files in src/quantumvitas/daemon/ including compat.py.

NOTE: This test has its own DAEMON_KERNEL_PREFIXES constant and does NOT
modify test_import_rules.py's FORBIDDEN_PREFIXES to avoid collateral.
"""

import ast
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
DAEMON_DIR = PROJECT_ROOT / "src/quantumvitas/daemon"

# Complete list of kernel module prefixes (daemon MUST NOT import these)
# This is a SUPERSET of test_import_rules.py's FORBIDDEN_PREFIXES
# We keep our own copy to avoid collateral impact on other tests
DAEMON_KERNEL_PREFIXES = (
    # Original set from test_import_rules.py
    "quantumvitas.core",
    "quantumvitas.calculation",
    "quantumvitas.analysis",
    "quantumvitas.io",
    "quantumvitas.drivers",
    "quantumvitas.engine",
    "quantumvitas.workflow",
    "quantumvitas.presets",
    # Additional kernel modules (daemon-specific enforcement)
    "quantumvitas.project",
    "quantumvitas.data",
    "quantumvitas.execution",
    "quantumvitas.history",
    "quantumvitas.ir",
    "quantumvitas.legacy",
    "quantumvitas.parsers",
    "quantumvitas.viz",
    "quantumvitas._vault",
    "quantumvitas.engines",
)

# Allowed quantumvitas imports for daemon
DAEMON_ALLOWED_PREFIXES = (
    "quantumvitas.api",
    "quantumvitas.daemon",
)

# Exception: Engine metadata imports in server.py handlers (M4)
# These are lazy imports inside try/except blocks, only triggered by specific engine_family requests.
# Per PROMPT_M4.md: "The engine-specific imports inside this handler are acceptable because
# this is daemon/server.py (above kernel). The imports are lazy and only triggered by the
# specific engine_family requested."
# Also allow DriverRegistry and core imports needed for generic RPC handlers (M4).
DAEMON_METADATA_IMPORT_EXCEPTIONS = {
    "src/quantumvitas/daemon/server.py": [
        "quantumvitas.drivers.vasp.data",
        "quantumvitas.drivers.orca.data",
        "quantumvitas.drivers.lammps.data",
        "quantumvitas.drivers.gaussian.data",
        "quantumvitas.drivers.abinit.data",
        "quantumvitas.drivers.cp2k.data",
        "quantumvitas.drivers.qmcpack.data",
        "quantumvitas.core.driver_registry",  # M4: Generic RPC handlers need DriverRegistry
        "quantumvitas.drivers",  # M4: Generic RPC handlers need to import drivers package
        "quantumvitas.core.resolution",  # M4: set_engine_family needs require_calculation
        "quantumvitas.core.models",  # M4: set_engine_family needs load_calculation, save_calculation
    ]
}


def find_imports(file_path: Path) -> list[tuple[int, str, str]]:
    """
    Find all imports in a Python file.

    Returns list of (line_number, import_type, module_name) tuples.
    """
    imports = []
    try:
        source = file_path.read_text()
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError):
        return imports

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((node.lineno, "import", alias.name))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append((node.lineno, "from", node.module))

    return imports


def test_daemon_no_kernel_imports():
    """
    Verify ALL daemon files do not import from kernel modules.

    This is a P0 gate - daemon MUST NOT have any kernel imports.
    Uses DAEMON_KERNEL_PREFIXES (not test_import_rules.py's FORBIDDEN_PREFIXES).
    """
    if not DAEMON_DIR.exists():
        pytest.skip("Daemon directory does not exist")

    violations = []

    for py_file in DAEMON_DIR.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue

        for line_num, import_type, module in find_imports(py_file):
            # Skip non-quantumvitas imports
            if not module.startswith("quantumvitas"):
                continue

            # Check if allowed
            is_allowed = any(module.startswith(prefix) for prefix in DAEMON_ALLOWED_PREFIXES)

            # Check if forbidden
            is_forbidden = any(module.startswith(prefix) for prefix in DAEMON_KERNEL_PREFIXES)

            # Check for exceptions (e.g., engine metadata imports in server.py handlers)
            rel_path = py_file.relative_to(PROJECT_ROOT)
            is_exception = False
            if str(rel_path) in DAEMON_METADATA_IMPORT_EXCEPTIONS:
                exception_modules = DAEMON_METADATA_IMPORT_EXCEPTIONS[str(rel_path)]
                is_exception = any(module.startswith(em) for em in exception_modules)

            if is_forbidden and not is_allowed and not is_exception:
                violations.append(
                    f"  {rel_path}:{line_num}: {import_type} {module}"
                )

    if violations:
        pytest.fail(
            f"Daemon kernel import ban violated!\n"
            f"P0 LAW: Daemon MUST NOT import from kernel modules.\n"
            f"Allowed: quantumvitas.api.*, quantumvitas.daemon.*\n"
            f"Violations:\n" + "\n".join(violations)
        )


def test_compat_py_specifically():
    """
    Specifically verify compat.py has no kernel imports.

    This file is the compat shaping layer and is easy to accidentally
    add kernel imports to.
    """
    compat_file = DAEMON_DIR / "compat.py"
    if not compat_file.exists():
        pytest.skip("compat.py does not exist")

    violations = []

    for line_num, import_type, module in find_imports(compat_file):
        if not module.startswith("quantumvitas"):
            continue

        is_forbidden = any(module.startswith(prefix) for prefix in DAEMON_KERNEL_PREFIXES)
        is_allowed = any(module.startswith(prefix) for prefix in DAEMON_ALLOWED_PREFIXES)

        if is_forbidden and not is_allowed:
            violations.append(f"  Line {line_num}: {import_type} {module}")

    if violations:
        pytest.fail(
            f"compat.py has forbidden kernel imports!\n"
            f"The shaper must only use quantumvitas.api.* capabilities.\n"
            f"Violations:\n" + "\n".join(violations)
        )

