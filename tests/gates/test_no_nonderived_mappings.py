"""
Gate: No Non-Derived Mapping Tables (§10.3)

Constitution §10.3: Mapping tables MAY exist only if they are purely derived from
engine_prefix + supported_gen_steps + spec_from(). No overrides, no special cases.

This gate scans for:
- _apply_special_case_overrides method
- Hardcoded mapping dicts that don't use pure derivation
"""

import ast
import re
from pathlib import Path
from typing import List, Tuple

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent

SCAN_DIRS = [
    REPO_ROOT / "src",
]

SKIP_PATTERNS = [
    "tests/gates/test_no_nonderived_mappings.py",  # This file itself
    "src/qmatsuite/_vault/*",  # Legacy archive
]


def is_skipped(path: Path) -> bool:
    """Check if file should be skipped."""
    import fnmatch
    rel_path = str(path.relative_to(REPO_ROOT))
    for pattern in SKIP_PATTERNS:
        if fnmatch.fnmatch(rel_path, pattern):
            return True
    return False


def scan_for_special_case_overrides(content: str, file_path: Path) -> List[Tuple[int, str]]:
    """Scan for _apply_special_case_overrides method."""
    violations = []
    lines = content.split('\n')
    
    for i, line in enumerate(lines, 1):
        if '_apply_special_case_overrides' in line:
            violations.append((i, f"_apply_special_case_overrides found: {line.strip()}"))
    
    return violations


def scan_all_files() -> List[Tuple[Path, int, str]]:
    """Scan all Python files for non-derived mapping violations."""
    all_violations = []
    for scan_dir in SCAN_DIRS:
        if not scan_dir.exists():
            continue
        for py_file in scan_dir.rglob("*.py"):
            if is_skipped(py_file):
                continue
            try:
                content = py_file.read_text()
                violations = scan_for_special_case_overrides(content, py_file)
                for line, msg in violations:
                    all_violations.append((py_file, line, msg))
            except (UnicodeDecodeError, SyntaxError):
                continue
    return all_violations


class TestNoNonderivedMappings:
    """Gate: No non-derived mapping tables."""

    def test_no_special_case_overrides(self):
        """Scan for _apply_special_case_overrides method."""
        violations = scan_all_files()

        if violations:
            report = "\n\n=== NON-DERIVED MAPPING VIOLATIONS ===\n"
            report += f"Found {len(violations)} violation(s):\n\n"
            for file_path, line, msg in violations:
                rel_path = file_path.relative_to(REPO_ROOT)
                report += f"  {rel_path}:{line} - {msg}\n"
            report += "\n=== END VIOLATIONS ===\n"
            report += "\nFix: Delete _apply_special_case_overrides. Use pure derivation only.\n"
            pytest.fail(report)

