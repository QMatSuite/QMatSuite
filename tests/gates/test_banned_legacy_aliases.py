"""
Gate: Banned Legacy Alias Values (§6)

Constitution §6: The following legacy values are FORBIDDEN as step type values:
- "w90_preproc" → MUST use "wannierprep" (gen) / "w90_wannierprep" (spec)
- "w90_run" → MUST use "wannier" (gen) / "w90_wannier" (spec)

Note: "pw2wannier90" MAY appear as an executable name, but MUST NOT appear as a step type value.
"""

import re
from pathlib import Path
from typing import List, Tuple

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent

SCAN_DIRS = [
    REPO_ROOT / "src",
    REPO_ROOT / "tests",
    REPO_ROOT / "tools",
]

SKIP_PATTERNS = [
    "tests/gates/test_banned_legacy_aliases.py",  # This file itself
    "src/qmatsuite/_vault/*",  # Legacy archive
]

# Banned step type values (as step type values, not executable names)
BANNED_VALUES = [
    "w90_preproc",
    "w90_run",
]


def is_skipped(path: Path) -> bool:
    """Check if file should be skipped."""
    import fnmatch
    rel_path = str(path.relative_to(REPO_ROOT))
    for pattern in SKIP_PATTERNS:
        if fnmatch.fnmatch(rel_path, pattern):
            return True
    return False


def scan_for_banned_aliases(content: str, file_path: Path) -> List[Tuple[int, str]]:
    """Scan for banned legacy alias values in step type contexts."""
    violations = []
    lines = content.split('\n')
    
    for i, line in enumerate(lines, 1):
        # Check for banned values as step type strings (in quotes)
        for banned in BANNED_VALUES:
            # Match as step type value: in quotes, or as dict key value, or in step_type assignments
            patterns = [
                rf'["\']{re.escape(banned)}["\']',  # String literal
                rf'step_type[^_]*\s*=\s*["\']{re.escape(banned)}["\']',  # Assignment
                rf'step_type_gen\s*=\s*["\']{re.escape(banned)}["\']',  # step_type_gen assignment
                rf'step_type_spec\s*=\s*["\']{re.escape(banned)}["\']',  # step_type_spec assignment
            ]
            for pattern in patterns:
                if re.search(pattern, line):
                    # Exclude executable names (e.g., "pw2wannier90.x")
                    if 'executable' in line.lower() or '.x' in line or 'exe' in line.lower():
                        continue
                    violations.append((i, f"Banned alias '{banned}' found: {line.strip()}"))
                    break
    
    return violations


def scan_all_files() -> List[Tuple[Path, int, str]]:
    """Scan all Python files for banned legacy alias violations."""
    all_violations = []
    for scan_dir in SCAN_DIRS:
        if not scan_dir.exists():
            continue
        for py_file in scan_dir.rglob("*.py"):
            if is_skipped(py_file):
                continue
            try:
                content = py_file.read_text()
                violations = scan_for_banned_aliases(content, py_file)
                for line, msg in violations:
                    all_violations.append((py_file, line, msg))
            except (UnicodeDecodeError, SyntaxError):
                continue
    return all_violations


class TestBannedLegacyAliases:
    """Gate: No banned legacy alias step type values."""

    def test_no_banned_aliases_in_code(self):
        """Scan for banned legacy alias values."""
        violations = scan_all_files()

        if violations:
            report = "\n\n=== BANNED LEGACY ALIAS VIOLATIONS ===\n"
            report += f"Found {len(violations)} violation(s):\n\n"
            for file_path, line, msg in violations:
                rel_path = file_path.relative_to(REPO_ROOT)
                report += f"  {rel_path}:{line} - {msg}\n"
            report += "\n=== END VIOLATIONS ===\n"
            report += "\nFix: Replace 'w90_preproc' with 'wannierprep'/'w90_wannierprep', "
            report += "'w90_run' with 'wannier'/'w90_wannier'.\n"
            pytest.fail(report)

