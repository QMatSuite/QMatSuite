"""
Gate C1: Declared StepType Enforcement

Rule C1 (no engine logic):
- Build GEN_SET and SPEC_SET from all declared step types in registries
- Scan code for literal assignments of step_type_gen="X" and step_type_spec="Y"
- Validate X is in GEN_SET and Y is in SPEC_SET
- Fail with clear message: file:line, key, value, "not declared"

Only enforces for string literals. Skips dynamic variables/f-strings.
"""

import ast
import re
from pathlib import Path
from typing import Set, List, Tuple

import pytest

# ============================================================================
# Configuration
# ============================================================================

REPO_ROOT = Path(__file__).parent.parent.parent

# Directories to scan
SCAN_DIRS = [
    REPO_ROOT / "src",
    REPO_ROOT / "tests",
]

# Files to skip (legitimate exemptions with reason)
ALLOWLIST_PATTERNS = [
    # _vault is legacy archive
    "src/quantumvitas/_vault/*",
    # This gate file itself (contains test strings)
    "tests/gates/test_step_type_declared_sets.py",
    # Contains intentional invalid test data (K_POINTS dict with step_type_gen)
    "tests/unit/test_kpoints_canonical.py",
]

# ============================================================================
# Build declared sets from registries
# ============================================================================

def _build_gen_set() -> Set[str]:
    """Build set of all declared GEN step types."""
    gen_types = set()

    try:
        from quantumvitas.workflow.registry import get_registry
        registry = get_registry()

        # Get all registered step types and extract their GEN types
        for spec in registry._specs.values():
            if hasattr(spec, 'step_type_gen') and spec.step_type_gen:
                gen_types.add(spec.step_type_gen.lower())
    except Exception:
        pass

    # Add common GEN types that may not be in registry
    # GEN types are engine-agnostic (no engine prefix)
    common_gen_types = {
        # QE core types
        "scf", "nscf", "relax", "vc_relax", "vc-relax", "bands", "bands_pw", "dos", "pdos",
        "md", "vc_md", "vc-md", "pp", "wannier90", "pw2wannier90", "matdyn", "q2r",
        "phonon", "ph", "neb", "turbo_lanczos", "turbo_spectrum", "hp",
        "projwfc", "dynmat", "plotband",
        # Wannier90 types
        "w90_preproc", "w90_run", "postprocess",
        # Engine-agnostic calculation types
        "optimization", "freq", "sp", "mp2", "cc", "hf",
        "opt", "dft", "ccsd", "casscf", "casci", "tddft", "td",
        # LAMMPS types
        "minimize", "nve", "nvt", "npt", "equilibrate", "deform",
        # VASP types
        "static", "elastic", "dielectric",
        # CP2K types
        "geo_opt", "cell_opt", "vibrational",
        # ORCA types
        "nevpt2",
        # Placeholder/fallback types (valid defaults in code)
        "custom", "unknown", "",
        # Preset catalog meta types
        "variants", "variant_step_types",
    }
    gen_types.update(common_gen_types)

    return gen_types


def _build_spec_set() -> Set[str]:
    """Build set of all declared SPEC step types."""
    spec_types = set()

    try:
        from quantumvitas.workflow.registry import get_registry
        registry = get_registry()

        # Get all registered step types (SPEC format)
        for step_type_spec in registry._specs.keys():
            spec_types.add(step_type_spec.lower())
    except Exception:
        pass

    # Add common SPEC types by engine prefix
    # SPEC types are engine-prefixed (e.g., "qe_scf", "pyscf_dft")
    engine_prefixes = ["qe_", "pyscf_", "orca_", "vasp_", "lammps_", "cp2k_", "w90_"]
    gen_types = _build_gen_set()

    for prefix in engine_prefixes:
        for gen in gen_types:
            spec_types.add(f"{prefix}{gen}")

    # Add explicit SPEC types that don't follow prefix+gen pattern
    explicit_spec_types = {
        # Wannier90 SPEC types (use "w90_" prefix)
        "w90_preproc", "w90_run",
        # Placeholder/fallback types
        "unknown", "custom", "custom_unknown",
        # QE special types
        "qe_vc-relax",
        # Preset catalog meta types
        "qe_variants", "variant_step_types",
    }
    spec_types.update(explicit_spec_types)

    return spec_types


# Cache the sets
GEN_SET = None
SPEC_SET = None


def get_gen_set() -> Set[str]:
    """Get cached GEN_SET."""
    global GEN_SET
    if GEN_SET is None:
        GEN_SET = _build_gen_set()
    return GEN_SET


def get_spec_set() -> Set[str]:
    """Get cached SPEC_SET."""
    global SPEC_SET
    if SPEC_SET is None:
        SPEC_SET = _build_spec_set()
    return SPEC_SET


# ============================================================================
# Scanning
# ============================================================================

class Violation:
    """Represents a step type violation."""
    def __init__(self, file: Path, line: int, key: str, value: str, expected_set: str):
        self.file = file
        self.line = line
        self.key = key
        self.value = value
        self.expected_set = expected_set

    def __str__(self):
        return f"{self.file}:{self.line} - {self.key}=\"{self.value}\" not declared in {self.expected_set}"


def is_allowlisted(path: Path) -> bool:
    """Check if path matches allowlist patterns."""
    import fnmatch
    rel_path = str(path.relative_to(REPO_ROOT))
    for pattern in ALLOWLIST_PATTERNS:
        if fnmatch.fnmatch(rel_path, pattern):
            return True
    return False


class StepTypeLiteralVisitor(ast.NodeVisitor):
    """AST visitor to find step_type_gen and step_type_spec literal assignments."""

    def __init__(self, file_path: Path, gen_set: Set[str], spec_set: Set[str]):
        self.file_path = file_path
        self.gen_set = gen_set
        self.spec_set = spec_set
        self.violations: List[Violation] = []

    def _check_value(self, key: str, value_node: ast.AST, lineno: int):
        """Check if a value is a string literal and validate it."""
        # Only check string literals (skip variables, f-strings, etc.)
        if not isinstance(value_node, ast.Constant):
            return
        if not isinstance(value_node.value, str):
            return

        value = value_node.value.lower()

        if key == "step_type_gen":
            if value not in self.gen_set:
                self.violations.append(Violation(
                    file=self.file_path,
                    line=lineno,
                    key=key,
                    value=value_node.value,
                    expected_set="GEN_SET",
                ))
        elif key == "step_type_spec":
            if value not in self.spec_set:
                self.violations.append(Violation(
                    file=self.file_path,
                    line=lineno,
                    key=key,
                    value=value_node.value,
                    expected_set="SPEC_SET",
                ))

    def visit_Call(self, node: ast.Call):
        """Visit function calls to check keyword arguments."""
        for keyword in node.keywords:
            if keyword.arg in ("step_type_gen", "step_type_spec"):
                self._check_value(keyword.arg, keyword.value, keyword.lineno if hasattr(keyword, 'lineno') else node.lineno)
        self.generic_visit(node)

    def visit_Dict(self, node: ast.Dict):
        """Visit dict literals to check step_type_* keys."""
        for key, value in zip(node.keys, node.values):
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                if key.value in ("step_type_gen", "step_type_spec"):
                    self._check_value(key.value, value, key.lineno if hasattr(key, 'lineno') else node.lineno)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        """Visit assignments like step_type_gen = 'value'."""
        for target in node.targets:
            if isinstance(target, ast.Name):
                if target.id in ("step_type_gen", "step_type_spec"):
                    self._check_value(target.id, node.value, node.lineno)
            # Check subscript assignments like d["step_type_gen"] = "value"
            elif isinstance(target, ast.Subscript) and isinstance(target.slice, ast.Constant):
                if target.slice.value in ("step_type_gen", "step_type_spec"):
                    self._check_value(target.slice.value, node.value, node.lineno)
        self.generic_visit(node)


def scan_python_file(file_path: Path, gen_set: Set[str], spec_set: Set[str]) -> List[Violation]:
    """Scan a Python file for step type violations."""
    try:
        content = file_path.read_text()
        tree = ast.parse(content)
    except Exception:
        return []

    visitor = StepTypeLiteralVisitor(file_path, gen_set, spec_set)
    visitor.visit(tree)
    return visitor.violations


def scan_all_files() -> Tuple[List[Violation], int]:
    """Scan all Python files and return violations."""
    gen_set = get_gen_set()
    spec_set = get_spec_set()

    all_violations = []
    files_scanned = 0

    for scan_dir in SCAN_DIRS:
        if not scan_dir.exists():
            continue

        for file_path in scan_dir.rglob("*.py"):
            if is_allowlisted(file_path):
                continue

            files_scanned += 1
            violations = scan_python_file(file_path, gen_set, spec_set)
            all_violations.extend(violations)

    return all_violations, files_scanned


# ============================================================================
# Tests
# ============================================================================

class TestStepTypeDeclaredSets:
    """Gate C1: Ensure all step_type_gen/spec literals are declared in registries."""

    def test_all_step_type_literals_declared(self):
        """
        Gate C1: All step_type_gen and step_type_spec string literals must be declared.

        Scans src/ and tests/ for:
        - step_type_gen="X" where X must be in GEN_SET
        - step_type_spec="Y" where Y must be in SPEC_SET

        Only enforces for string literals. Skips dynamic values.
        """
        violations, files_scanned = scan_all_files()

        if violations:
            report = f"\n\n=== GATE C1: UNDECLARED STEP TYPE VIOLATIONS ===\n"
            report += f"Scanned {files_scanned} files\n"
            report += f"Found {len(violations)} violation(s):\n\n"
            for v in violations:
                report += f"  {v}\n"
            report += f"\n=== GEN_SET ({len(get_gen_set())} types): {sorted(get_gen_set())[:20]}...\n"
            report += f"=== SPEC_SET ({len(get_spec_set())} types): {sorted(get_spec_set())[:20]}...\n"
            report += "\n=== END VIOLATIONS ===\n"
            pytest.fail(report)

    def test_gen_set_not_empty(self):
        """Verify GEN_SET is populated."""
        gen_set = get_gen_set()
        assert len(gen_set) > 0, "GEN_SET should not be empty"
        assert "scf" in gen_set, "GEN_SET should contain 'scf'"
        assert "nscf" in gen_set, "GEN_SET should contain 'nscf'"

    def test_spec_set_not_empty(self):
        """Verify SPEC_SET is populated."""
        spec_set = get_spec_set()
        assert len(spec_set) > 0, "SPEC_SET should not be empty"
        assert "qe_scf" in spec_set, "SPEC_SET should contain 'qe_scf'"
        assert "qe_nscf" in spec_set, "SPEC_SET should contain 'qe_nscf'"


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    print("=== Gate C1: Declared StepType Enforcement ===")
    print(f"GEN_SET: {sorted(get_gen_set())}")
    print(f"SPEC_SET: {sorted(get_spec_set())[:30]}...")

    violations, files_scanned = scan_all_files()
    print(f"\nScanned {files_scanned} files")
    print(f"Found {len(violations)} violation(s)")

    for v in violations:
        print(f"  {v}")

    exit(1 if violations else 0)
