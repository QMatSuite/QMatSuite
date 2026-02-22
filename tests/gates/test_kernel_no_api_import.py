"""
Gate test G-K0: Kernel packages MUST NOT import from qmatsuite.api.

This enforces the dependency direction: api → kernel, never kernel → api.
Uses the AST-based ImportScanner from _import_scan.py for accurate detection.

Allowlist tracks known violations that are being fixed in subsequent PRs.
The allowlist MUST shrink to zero after PR-K1.
"""

from pathlib import Path

import pytest

from tests.gates._import_scan import ImportScanner, Violation

# Root of the source tree
SRC_ROOT = Path(__file__).parent.parent.parent / "src" / "qmatsuite"

# All kernel packages to scan
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
    "qmatsuite.api",
)

# Known violations allowlist: set of "relative_path:line_number" strings.
# Each entry represents a known violation that is scheduled for removal.
# This set MUST be empty after PR-K1 lands.
ALLOWLIST: set[str] = set()


def _relative_key(violation: Violation) -> str:
    """Build a 'relative_path:line' key for allowlist matching."""
    try:
        rel = violation.file_path.relative_to(SRC_ROOT)
    except ValueError:
        rel = violation.file_path
    return f"{rel}:{violation.line_number}"


def test_kernel_no_api_import():
    """Kernel packages must not import from qmatsuite.api."""
    scanner = ImportScanner(forbidden_prefixes=FORBIDDEN_PREFIXES)

    all_violations: list[Violation] = []
    for pkg in KERNEL_PACKAGES:
        pkg_dir = SRC_ROOT / pkg
        if pkg_dir.exists():
            all_violations.extend(scanner.scan_directory(pkg_dir))

    # Subtract allowlisted violations
    unexpected = [v for v in all_violations if _relative_key(v) not in ALLOWLIST]

    if unexpected:
        lines = [f"\nG-K0 FAILED: {len(unexpected)} unexpected kernel → api import(s):\n"]
        for v in sorted(unexpected, key=lambda v: (str(v.file_path), v.line_number)):
            lines.append(f"  {_relative_key(v)}  ({v.import_type} {v.module_name})")
        lines.append("")
        lines.append("Fix: Replace with direct kernel-level imports (e.g. gen_from from workflow.step_type_convert).")
        lines.append("Or add to ALLOWLIST if this is a known, tracked violation.")
        pytest.fail("\n".join(lines))

    # Also warn about stale allowlist entries
    found_keys = {_relative_key(v) for v in all_violations}
    stale = ALLOWLIST - found_keys
    if stale:
        lines = [f"\nG-K0 WARNING: {len(stale)} stale allowlist entry/entries (violations already fixed):\n"]
        for s in sorted(stale):
            lines.append(f"  {s}")
        lines.append("\nRemove these from ALLOWLIST in test_kernel_no_api_import.py.")
        pytest.fail("\n".join(lines))
