"""
Gate test G-K6: Engine packages MUST NOT import SSOT infrastructure or call yaml.safe_load.

Engines receive all data via EngineInput (after PR-K4). They must not:
1. Import SSOT infrastructure (yaml_io, yamldoc, locking, journal)
2. Call yaml.safe_load on YAML file paths

This gate enforces Law K6 from KERNEL_DEPENDENCY_SPEC.md.
"""

import ast
import re
from pathlib import Path

import pytest

from tests.gates._import_scan import ImportScanner, Violation

# Root of the source tree
SRC_ROOT = Path(__file__).parent.parent.parent / "src" / "qmatsuite"
ENGINE_DIR = SRC_ROOT / "engine"

# --- Check 1: Forbidden SSOT imports ---

FORBIDDEN_IMPORT_PREFIXES = (
    "qmatsuite.core.yaml_io",
    "qmatsuite.core.yamldoc",
    "qmatsuite.core.locking",
    "qmatsuite.core.journal",
)

# No known import violations expected
IMPORT_ALLOWLIST: set[str] = set()

# --- Check 2: Forbidden yaml.safe_load patterns ---

# Allowlist for yaml.safe_load calls: "relative_path:line_number"
# These are known violations scheduled for removal in PR-K4.
YAML_LOAD_ALLOWLIST: set[str] = {
    "engine/pyscf_engine.py:652",
    "engine/pyscf_engine.py:779",
    "engine/orca_engine.py:669",
    "engine/orca_engine.py:684",
    "engine/psi4_engine.py:435",
    "engine/psi4_engine.py:516",
}

# Regex pattern to detect yaml.safe_load calls
YAML_SAFE_LOAD_RE = re.compile(r"yaml\.safe_load\s*\(")


def _relative_key_from_path(file_path: Path, line_number: int) -> str:
    """Build a 'relative_path:line' key for allowlist matching."""
    try:
        rel = file_path.relative_to(SRC_ROOT)
    except ValueError:
        rel = file_path
    return f"{rel}:{line_number}"


def _relative_key(violation: Violation) -> str:
    """Build a 'relative_path:line' key for allowlist matching."""
    return _relative_key_from_path(violation.file_path, violation.line_number)


def _find_yaml_safe_load_calls(directory: Path) -> list[tuple[Path, int, str]]:
    """
    Find yaml.safe_load calls using AST analysis for accuracy.

    Returns list of (file_path, line_number, source_line) tuples.
    """
    results = []
    if not directory.exists():
        return results

    for py_file in directory.rglob("*.py"):
        try:
            source = py_file.read_text(encoding="utf-8")
        except Exception:
            continue

        # Use line-by-line regex for yaml.safe_load detection
        # (AST doesn't easily distinguish yaml.safe_load from other method calls)
        for i, line in enumerate(source.splitlines(), start=1):
            if YAML_SAFE_LOAD_RE.search(line):
                results.append((py_file, i, line.strip()))

    return results


def test_engine_no_ssot_import():
    """Engine packages must not import SSOT infrastructure modules."""
    scanner = ImportScanner(forbidden_prefixes=FORBIDDEN_IMPORT_PREFIXES)

    all_violations = scanner.scan_directory(ENGINE_DIR)

    # Subtract allowlisted violations
    unexpected = [v for v in all_violations if _relative_key(v) not in IMPORT_ALLOWLIST]

    if unexpected:
        lines = [f"\nG-K6 (imports) FAILED: {len(unexpected)} forbidden SSOT import(s) in engine/:\n"]
        for v in sorted(unexpected, key=lambda v: (str(v.file_path), v.line_number)):
            lines.append(f"  {_relative_key(v)}  ({v.import_type} {v.module_name})")
        lines.append("")
        lines.append("Fix: Engines must receive data via EngineInput, not import SSOT modules.")
        pytest.fail("\n".join(lines))

    # Warn about stale allowlist entries
    found_keys = {_relative_key(v) for v in all_violations}
    stale = IMPORT_ALLOWLIST - found_keys
    if stale:
        lines = [f"\nG-K6 (imports) WARNING: {len(stale)} stale allowlist entry/entries:\n"]
        for s in sorted(stale):
            lines.append(f"  {s}")
        pytest.fail("\n".join(lines))


def test_engine_no_yaml_safe_load():
    """Engine packages must not call yaml.safe_load on file paths."""
    hits = _find_yaml_safe_load_calls(ENGINE_DIR)

    # Subtract allowlisted hits
    unexpected = [
        (fp, ln, src) for fp, ln, src in hits
        if _relative_key_from_path(fp, ln) not in YAML_LOAD_ALLOWLIST
    ]

    if unexpected:
        lines = [f"\nG-K6 (yaml.safe_load) FAILED: {len(unexpected)} unexpected yaml.safe_load call(s) in engine/:\n"]
        for fp, ln, src in sorted(unexpected, key=lambda x: (str(x[0]), x[1])):
            key = _relative_key_from_path(fp, ln)
            lines.append(f"  {key}:  {src}")
        lines.append("")
        lines.append("Fix: Engines must receive data via EngineInput, not read YAML files directly.")
        pytest.fail("\n".join(lines))

    # Warn about stale allowlist entries
    found_keys = {_relative_key_from_path(fp, ln) for fp, ln, _ in hits}
    stale = YAML_LOAD_ALLOWLIST - found_keys
    if stale:
        lines = [f"\nG-K6 (yaml.safe_load) WARNING: {len(stale)} stale allowlist entry/entries:\n"]
        for s in sorted(stale):
            lines.append(f"  {s}")
        lines.append("\nRemove these from YAML_LOAD_ALLOWLIST in test_engine_no_ssot_import.py.")
        pytest.fail("\n".join(lines))
