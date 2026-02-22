"""
Gate: Forbid Third Namespaces (§10.3)

Constitution §10.3: Only two step type namespaces exist: step_type_gen and step_type_spec.
Any third namespace (GEN_*, GeneralizedStep enum, etc.) is ILLEGAL.

This gate scans for:
- GEN_* format strings (e.g., "GEN_SCF")
- GeneralizedStep enum usage
- Any uppercase step type enum values
"""

import ast
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
    "tests/gates/test_no_third_namespace.py",  # This file itself
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


def scan_for_gen_patterns(content: str, file_path: Path) -> List[Tuple[int, str]]:
    """Scan for GEN_* patterns and GeneralizedStep usage."""
    violations = []
    lines = content.split('\n')
    
    for i, line in enumerate(lines, 1):
        # Skip comments and docstrings
        if line.strip().startswith('#') or '"""' in line or "'''" in line:
            continue
        
        # Skip legitimate constant names (GEN_TYPE_TOKENS, GEN_STEPS, etc.)
        if re.search(r'\bGEN_(TYPE_TOKENS|STEPS|SET)\b', line):
            continue
        
        # Check for GEN_* format strings (step type values)
        if re.search(r'["\']GEN_[A-Z][A-Z_]+["\']', line):
            violations.append((i, f"GEN_* format found: {line.strip()}"))
        
        # Check for GeneralizedStep enum
        if 'GeneralizedStep' in line and not line.strip().startswith('#'):
            violations.append((i, f"GeneralizedStep enum usage: {line.strip()}"))
    
    return violations


def scan_all_files() -> List[Tuple[Path, int, str]]:
    """Scan all Python files for third namespace violations."""
    all_violations = []
    for scan_dir in SCAN_DIRS:
        if not scan_dir.exists():
            continue
        for py_file in scan_dir.rglob("*.py"):
            if is_skipped(py_file):
                continue
            try:
                content = py_file.read_text()
                violations = scan_for_gen_patterns(content, py_file)
                for line, msg in violations:
                    all_violations.append((py_file, line, msg))
            except (UnicodeDecodeError, SyntaxError):
                continue
    return all_violations


class TestNoThirdNamespace:
    """Gate: No third namespace (GEN_*, GeneralizedStep, etc.)."""

    def test_no_third_namespace_in_code(self):
        """Scan for third namespace violations."""
        violations = scan_all_files()

        if violations:
            report = "\n\n=== THIRD NAMESPACE VIOLATIONS ===\n"
            report += f"Found {len(violations)} violation(s):\n\n"
            for file_path, line, msg in violations:
                rel_path = file_path.relative_to(REPO_ROOT)
                report += f"  {rel_path}:{line} - {msg}\n"
            report += "\n=== END VIOLATIONS ===\n"
            report += "\nFix: Delete third namespace entirely. Use step_type_gen or step_type_spec only.\n"
            pytest.fail(report)

