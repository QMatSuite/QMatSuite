"""
Gate B5: No SPEC in Preset/ParamSpace Layer (§8)

Constitution §8: UI/Preset/ParamSpace/Workflow Templates MUST use step_type_gen ONLY.
step.yaml/Runner/Dispatch/Execution MUST use step_type_spec ONLY.

This gate scans preset/paramspace/workflow code for SPEC strings (containing _).
"""

import re
from pathlib import Path
from typing import List, Tuple

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent

# Directories that MUST use GEN only (no SPEC)
GEN_ONLY_DIRS = [
    REPO_ROOT / "src" / "quantumvitas" / "presets",
    REPO_ROOT / "src" / "quantumvitas" / "workflow" / "templates.py",
]

# Known engine prefixes (for detecting SPEC strings)
ENGINE_PREFIXES = {"qe", "vasp", "pyscf", "orca", "lammps", "cp2k", "w90"}

SKIP_PATTERNS = [
    "tests/gates/test_no_spec_in_preset_layer.py",  # This file itself
    "src/quantumvitas/_vault/*",  # Legacy archive
]


def is_skipped(path: Path) -> bool:
    """Check if file should be skipped."""
    import fnmatch
    rel_path = str(path.relative_to(REPO_ROOT))
    for pattern in SKIP_PATTERNS:
        if fnmatch.fnmatch(rel_path, pattern):
            return True
    return False


def is_spec_string(s: str) -> bool:
    """Check if string looks like a SPEC step type (engine_prefix_gen)."""
    if not s or "_" not in s:
        return False
    parts = s.split("_", 1)
    if len(parts) != 2:
        return False
    prefix, gen = parts
    return prefix.lower() in ENGINE_PREFIXES


def scan_for_spec_strings(content: str, file_path: Path) -> List[Tuple[int, str]]:
    """Scan for SPEC strings in GEN-only layer."""
    violations = []
    lines = content.split('\n')
    
    for i, line in enumerate(lines, 1):
        # Skip comments
        if line.strip().startswith('#'):
            continue
        
        # Look for SPEC strings in step type contexts
        # Pattern: step type assignments, dict keys, function calls with step types
        patterns = [
            r'["\']([a-z]+_[a-z]+)["\']',  # String literals like "qe_scf"
            r'step_type[^_]*\s*=\s*["\']([a-z]+_[a-z]+)["\']',  # step_type = "qe_scf"
            r'applies_to_step_types\s*=\s*.*["\']([a-z]+_[a-z]+)["\']',  # preset variants
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, line, re.IGNORECASE)
            for match in matches:
                candidate = match.group(1) if match.lastindex else match.group(0).strip('"\'')
                if is_spec_string(candidate):
                    # Exclude if it's clearly in a comment or docstring
                    if '#' in line and line.index('#') < match.start():
                        continue
                    violations.append((i, f"SPEC string '{candidate}' found: {line.strip()}"))
    
    return violations


def scan_all_files() -> List[Tuple[Path, int, str]]:
    """Scan GEN-only layer files for SPEC string violations."""
    all_violations = []
    for gen_only_dir in GEN_ONLY_DIRS:
        if not gen_only_dir.exists():
            continue
        if gen_only_dir.is_file():
            files = [gen_only_dir]
        else:
            files = list(gen_only_dir.rglob("*.py"))
        
        for py_file in files:
            if is_skipped(py_file):
                continue
            try:
                content = py_file.read_text()
                violations = scan_for_spec_strings(content, py_file)
                for line, msg in violations:
                    all_violations.append((py_file, line, msg))
            except (UnicodeDecodeError, SyntaxError):
                continue
    return all_violations


class TestNoSpecInPresetLayer:
    """Gate B5: No SPEC strings in preset/paramspace/workflow layer."""

    def test_no_spec_in_preset_layer(self):
        """Scan preset/paramspace/workflow code for SPEC strings."""
        violations = scan_all_files()

        if violations:
            report = "\n\n=== SPEC IN PRESET LAYER VIOLATIONS ===\n"
            report += f"Found {len(violations)} violation(s):\n\n"
            report += "The preset/paramspace/workflow layer MUST use step_type_gen only.\n"
            report += "SPEC strings (containing _) are FORBIDDEN in this layer.\n\n"
            for file_path, line, msg in violations:
                rel_path = file_path.relative_to(REPO_ROOT)
                report += f"  {rel_path}:{line} - {msg}\n"
            report += "\n=== END VIOLATIONS ===\n"
            report += "\nFix: Convert SPEC strings to GEN using gen_from() or use step_type_gen directly.\n"
            pytest.fail(report)

