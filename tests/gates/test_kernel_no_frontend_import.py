"""
Gate test G-K1: Kernel packages MUST NOT import from CLI or daemon layers.

This enforces the dependency direction: frontends → api → kernel.
Kernel code must never depend on CLI or daemon packages.
"""

from pathlib import Path

import pytest

from tests.gates._import_scan import ImportScanner, Violation

# Root of the source tree
SRC_ROOT = Path(__file__).parent.parent.parent / "src" / "qmatsuite"

# All kernel packages to scan (same as G-K0)
KERNEL_PACKAGES = [
    "core",
    "calculation",
    "execution",
    "engine",
    "workflow",
    "analysis",
    "io",
    "presets",
    "parsers",
    "history",
    "project",
    "data",
    "drivers",
    "ir",
    "viz",
    "legacy",
]

# Forbidden import prefixes
FORBIDDEN_PREFIXES = (
    "qmatsuite.cli",
    "qmatsuite.daemon",
)

# No known violations expected
ALLOWLIST: set[str] = set()


def _relative_key(violation: Violation) -> str:
    """Build a 'relative_path:line' key for allowlist matching."""
    try:
        rel = violation.file_path.relative_to(SRC_ROOT)
    except ValueError:
        rel = violation.file_path
    return f"{rel}:{violation.line_number}"


def test_kernel_no_frontend_import():
    """Kernel packages must not import from qmatsuite.cli or qmatsuite.daemon."""
    scanner = ImportScanner(forbidden_prefixes=FORBIDDEN_PREFIXES)

    all_violations: list[Violation] = []
    for pkg in KERNEL_PACKAGES:
        pkg_dir = SRC_ROOT / pkg
        if pkg_dir.exists():
            all_violations.extend(scanner.scan_directory(pkg_dir))

    # Subtract allowlisted violations
    unexpected = [v for v in all_violations if _relative_key(v) not in ALLOWLIST]

    if unexpected:
        lines = [f"\nG-K1 FAILED: {len(unexpected)} unexpected kernel → frontend import(s):\n"]
        for v in sorted(unexpected, key=lambda v: (str(v.file_path), v.line_number)):
            lines.append(f"  {_relative_key(v)}  ({v.import_type} {v.module_name})")
        lines.append("")
        lines.append("Fix: Kernel code must not import from CLI or daemon layers.")
        pytest.fail("\n".join(lines))

    # Warn about stale allowlist entries
    found_keys = {_relative_key(v) for v in all_violations}
    stale = ALLOWLIST - found_keys
    if stale:
        lines = [f"\nG-K1 WARNING: {len(stale)} stale allowlist entry/entries:\n"]
        for s in sorted(stale):
            lines.append(f"  {s}")
        lines.append("\nRemove these from ALLOWLIST in test_kernel_no_frontend_import.py.")
        pytest.fail("\n".join(lines))
