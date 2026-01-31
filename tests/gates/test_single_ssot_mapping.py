"""
Gate B6: Single SSOT for Mappings (§10.3)

Constitution §10.3: All mapping lookups must call DriverRegistry or GenStepRegistry.
No duplicate mapping dicts in tests/tools.

This gate scans tests and tools for copied mapping dicts that duplicate SSOT.
"""

import ast
import re
from pathlib import Path
from typing import List, Tuple, Set

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent

SCAN_DIRS = [
    REPO_ROOT / "tests",
    REPO_ROOT / "tools",
]

SKIP_PATTERNS = [
    "tests/gates/test_single_ssot_mapping.py",  # This file itself
    "tests/fixtures/*",  # Fixture files may have test data
]

# Known engine prefixes and gen steps (for detecting mapping dicts)
ENGINE_PREFIXES = {"qe", "vasp", "pyscf", "orca", "lammps", "cp2k", "w90"}
COMMON_GEN_STEPS = {"scf", "nscf", "relax", "md", "dos", "bands", "bandspw", "wannierprep", "pw2wannier", "wannier"}


def is_skipped(path: Path) -> bool:
    """Check if file should be skipped."""
    import fnmatch
    rel_path = str(path.relative_to(REPO_ROOT))
    for pattern in SKIP_PATTERNS:
        if fnmatch.fnmatch(rel_path, pattern):
            return True
    return False


def looks_like_mapping_dict(line: str) -> bool:
    """Check if line looks like a step type mapping dict entry."""
    # Pattern: "gen": "prefix_gen" or "prefix_gen": "gen"
    patterns = [
        r'["\']([a-z]+)["\']\s*:\s*["\']([a-z]+_[a-z]+)["\']',  # "scf": "qe_scf"
        r'["\']([a-z]+_[a-z]+)["\']\s*:\s*["\']([a-z]+)["\']',  # "qe_scf": "scf"
    ]
    for pattern in patterns:
        if re.search(pattern, line):
            return True
    return False


def scan_for_mapping_dicts(content: str, file_path: Path) -> List[Tuple[int, str]]:
    """Scan for hardcoded mapping dicts."""
    violations = []
    lines = content.split('\n')
    
    in_dict = False
    dict_start_line = 0
    dict_lines = []
    
    for i, line in enumerate(lines, 1):
        # Detect dict start
        if '{' in line and ('MATERIALIZATION' in line.upper() or 'MAPPING' in line.upper() or looks_like_mapping_dict(line)):
            in_dict = True
            dict_start_line = i
            dict_lines = [line]
        elif in_dict:
            dict_lines.append(line)
            # Detect dict end
            if '}' in line:
                # Check if this looks like a step type mapping dict
                dict_content = '\n'.join(dict_lines)
                if any(gen in dict_content and f"{prefix}_{gen}" in dict_content 
                       for gen in COMMON_GEN_STEPS for prefix in ENGINE_PREFIXES):
                    violations.append((
                        dict_start_line,
                        f"Hardcoded mapping dict found (lines {dict_start_line}-{i}). Use DriverRegistry or GenStepRegistry instead."
                    ))
                in_dict = False
                dict_lines = []
    
    return violations


def scan_all_files() -> List[Tuple[Path, int, str]]:
    """Scan tests and tools for duplicate mapping dicts."""
    all_violations = []
    for scan_dir in SCAN_DIRS:
        if not scan_dir.exists():
            continue
        for py_file in scan_dir.rglob("*.py"):
            if is_skipped(py_file):
                continue
            try:
                content = py_file.read_text()
                violations = scan_for_mapping_dicts(content, py_file)
                for line, msg in violations:
                    all_violations.append((py_file, line, msg))
            except (UnicodeDecodeError, SyntaxError):
                continue
    return all_violations


class TestSingleSSOTMapping:
    """Gate B6: Single SSOT for mappings."""

    def test_no_duplicate_mapping_dicts(self):
        """Scan for duplicate mapping dicts in tests/tools."""
        violations = scan_all_files()

        if violations:
            report = "\n\n=== DUPLICATE MAPPING DICT VIOLATIONS ===\n"
            report += f"Found {len(violations)} violation(s):\n\n"
            report += "Tests and tools MUST NOT contain hardcoded mapping dicts.\n"
            report += "All mapping lookups must call DriverRegistry or GenStepRegistry (SSOT).\n\n"
            for file_path, line, msg in violations:
                rel_path = file_path.relative_to(REPO_ROOT)
                report += f"  {rel_path}:{line} - {msg}\n"
            report += "\n=== END VIOLATIONS ===\n"
            report += "\nFix: Replace hardcoded dicts with DriverRegistry.get_step_type_spec() or GenStepRegistry calls.\n"
            pytest.fail(report)

