"""
Gate: No Manual Join/Split

Constitution Section 3.1: All step type conversions MUST use canonical functions:
- spec_from(prefix, gen) for join
- gen_from(spec) for split (returns gen)
- prefix_from(spec) for split (returns prefix)

FORBIDDEN in runtime code:
- .split("_", 1) for step type parsing
- f"{prefix}_{gen}" for step type construction (outside step_type_convert.py)
"""

import re
from pathlib import Path
from typing import List, Tuple

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent

# Directories to scan
SCAN_DIRS = [
    REPO_ROOT / "src",
]

# Files to skip (canonical implementation)
ALLOWLIST_PATTERNS = [
    # Canonical implementation of split functions
    "src/quantumvitas/workflow/step_type_convert.py",
    # Legacy archive
    "src/quantumvitas/_vault/*",
    # Non step-type splitting (slug/filename parsing)
    "src/quantumvitas/calculation/compat_executor.py",  # calculation_slug parsing
    "src/quantumvitas/core/pseudo_config.py",  # filename parsing
]


def is_allowlisted(path: Path) -> bool:
    """Check if path matches allowlist patterns."""
    import fnmatch
    rel_path = str(path.relative_to(REPO_ROOT))
    for pattern in ALLOWLIST_PATTERNS:
        if fnmatch.fnmatch(rel_path, pattern):
            return True
    return False


def scan_for_manual_split(file_path: Path) -> List[Tuple[int, str]]:
    """Scan file for manual .split("_") calls in step type context."""
    violations = []
    try:
        content = file_path.read_text()
        lines = content.split('\n')

        # Pattern: .split("_" or .split('_'
        pattern = r'\.split\s*\(\s*["\']_'

        for i, line in enumerate(lines, 1):
            if re.search(pattern, line):
                # Check if it's in step_type context by looking at surrounding context
                line_lower = line.lower()
                # Check for step type related context
                step_type_context = any(ctx in line_lower for ctx in [
                    'step_type', 'spec', 'gen_type', 'engine_prefix',
                    'machine_step', 'step_type_str'
                ])
                # Check for non-step-type context (should be allowlisted)
                non_step_context = any(ctx in line_lower for ctx in [
                    'filename', 'path', 'slug', 'calculation_slug', 'folder'
                ])

                if step_type_context and not non_step_context:
                    violations.append((i, line.strip()))

    except Exception:
        pass

    return violations


def scan_all_files() -> List[Tuple[Path, int, str]]:
    """Scan all files for violations."""
    all_violations = []

    for scan_dir in SCAN_DIRS:
        if not scan_dir.exists():
            continue

        for file_path in scan_dir.rglob("*.py"):
            if is_allowlisted(file_path):
                continue

            violations = scan_for_manual_split(file_path)
            for line_num, line in violations:
                all_violations.append((file_path, line_num, line))

    return all_violations


class TestNoManualJoinSplit:
    """Gate: No manual join/split operations for step types."""

    def test_no_manual_split_for_step_types(self):
        """
        Gate: All step type parsing must use canonical functions.

        Constitution Section 3.1 prohibits:
        - .split("_", 1) for step type parsing
        - Manual underscore parsing

        Required: Use gen_from(), prefix_from() from step_type_convert.py
        """
        violations = scan_all_files()

        if violations:
            report = "\n\n=== GATE: NO MANUAL JOIN/SPLIT VIOLATIONS ===\n"
            report += f"Found {len(violations)} violation(s):\n\n"
            for path, line_num, line in violations:
                rel_path = path.relative_to(REPO_ROOT)
                report += f"  {rel_path}:{line_num}\n"
                report += f"    {line}\n\n"
            report += "=== FIX ===\n"
            report += "Use canonical functions from step_type_convert.py:\n"
            report += "  - gen_from(spec) to extract GEN from SPEC\n"
            report += "  - prefix_from(spec) to extract engine prefix from SPEC\n"
            report += "  - spec_from(prefix, gen) to create SPEC from prefix + GEN\n"
            report += "\n=== END VIOLATIONS ===\n"
            pytest.fail(report)


if __name__ == "__main__":
    print("=== Gate: No Manual Join/Split ===")
    violations = scan_all_files()
    print(f"Found {len(violations)} violation(s)")
    for path, line_num, line in violations:
        rel_path = path.relative_to(REPO_ROOT)
        print(f"  {rel_path}:{line_num} - {line}")
    exit(1 if violations else 0)
