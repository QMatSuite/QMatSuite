"""
Gate 0.2: Legacy Import Detector

Ensures no production code imports from legacy modules.
"""

import re
from pathlib import Path


LEGACY_PATTERNS = [
    r"from qmatsuite\._api_legacy import",
    r"from qmatsuite\.api_legacy import",
    r"from qmatsuite\._vault import",
    r"import qmatsuite\._api_legacy",
    r"import qmatsuite\.api_legacy",
    r"import qmatsuite\._vault",
]


def test_no_legacy_imports():
    """Ensure no production code or tests import from legacy modules."""
    violations = []
    
    # Check src/ directory
    src = Path("src/qmatsuite")
    for py_file in src.rglob("*.py"):
        # Skip vault directory (it's allowed to import itself for reference, but will be deleted)
        if "_vault" in str(py_file):
            continue
        # Skip migration tooling (plan says migration tooling only may touch vault)
        if "migration_" in py_file.name:
            continue

        try:
            content = py_file.read_text(encoding="utf-8")
            lines = content.split("\n")
            
            for i, line in enumerate(lines, 1):
                for pattern in LEGACY_PATTERNS:
                    if re.search(pattern, line):
                        rel_path = py_file.relative_to(Path("src"))
                        violations.append(f"{rel_path}:{i}: {line.strip()}")
                        break  # Only report once per line
        except (UnicodeDecodeError, Exception):
            # Skip files that can't be read
            continue
    
    # Check tests/ directory (excluding gate tests that check for these patterns)
    tests = Path("tests")
    for py_file in tests.rglob("*.py"):
        # Skip gate test that checks for these patterns
        if py_file.name == "test_no_legacy_imports.py":
            continue

        try:
            content = py_file.read_text(encoding="utf-8")
            lines = content.split("\n")
            
            for i, line in enumerate(lines, 1):
                for pattern in LEGACY_PATTERNS:
                    if re.search(pattern, line):
                        rel_path = py_file.relative_to(Path("."))
                        violations.append(f"{rel_path}:{i}: {line.strip()}")
                        break  # Only report once per line
        except (UnicodeDecodeError, Exception):
            # Skip files that can't be read
            continue

    if violations:
        error_msg = "ERROR: Legacy import detected in production code or tests:\n"
        for violation in violations:
            error_msg += f"  - {violation}\n"
        error_msg += "\nProduction code and tests must not import from qmatsuite._vault"
        assert False, error_msg

