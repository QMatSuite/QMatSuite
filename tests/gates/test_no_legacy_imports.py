"""
Gate 0.2: Legacy Import Detector

Ensures no production code imports from legacy modules.
"""

import re
from pathlib import Path


LEGACY_PATTERNS = [
    r"from quantumvitas\._api_legacy import",
    r"from quantumvitas\.api_legacy import",
    r"from quantumvitas\._vault import",
    r"import quantumvitas\._api_legacy",
    r"import quantumvitas\.api_legacy",
    r"import quantumvitas\._vault",
]


def test_no_legacy_imports():
    """Ensure no production code imports from legacy modules."""
    src = Path("src/quantumvitas")
    violations = []

    for py_file in src.rglob("*.py"):
        # Skip vault directory (it's allowed to import itself for reference)
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

    if violations:
        error_msg = "ERROR: Legacy import detected in production code:\n"
        for violation in violations:
            error_msg += f"  - {violation}\n"
        error_msg += "\nProduction code must only import from quantumvitas.api"
        assert False, error_msg

