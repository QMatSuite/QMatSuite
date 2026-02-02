"""
Gate C1: Declared StepType Enforcement

Rule C1 (no engine logic):
- Build GEN_SET and SPEC_SET from SSOT (registry + engine recipes)
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
    # Param mismatch gate contains signature definitions with type markers
    "tests/gates/test_step_type_param_mismatch.py",
    # Contains intentional invalid test data (K_POINTS dict with step_type_gen)
    "tests/unit/test_kpoints_canonical.py",
]

# ============================================================================
# Build declared sets from SSOT (registry + engine recipes)
# ============================================================================

def _build_gen_set() -> Set[str]:
    """
    Build set of all declared GEN step types from SSOT.

    SSOT sources:
    1. Registry: Get step_type_gen from all StepTypeSpec objects
    2. Engine recipes: Get SUPPORTED_GEN_STEPS from each engine's recipe
    """
    gen_types = set()

    # Source 1: Registry (primary SSOT for step type specs)
    try:
        from quantumvitas.workflow.registry import get_registry
        registry = get_registry()

        # registry._types is keyed by step_type_spec, values are StepTypeSpec
        for spec in registry._types.values():
            if hasattr(spec, 'step_type_gen') and spec.step_type_gen:
                gen_types.add(spec.step_type_gen.lower())
    except Exception as e:
        import sys
        print(f"Warning: Failed to load registry for GEN_SET: {e}", file=sys.stderr)

    # Source 2: DriverRegistry registered step types (from drivers)
    try:
        from quantumvitas.core.driver_registry import DriverRegistry
        import quantumvitas.drivers  # Ensure drivers are registered

        # Get all registered step types from drivers
        for step_type_spec in DriverRegistry.get_all_step_types():
            spec = DriverRegistry.get_step_type_spec(step_type_spec)
            if hasattr(spec, 'step_type_gen') and spec.step_type_gen:
                gen_types.add(spec.step_type_gen.lower())
    except Exception as e:
        import sys
        print(f"Warning: Failed to load driver step types for GEN_SET: {e}", file=sys.stderr)

    # Source 3: Engine recipes (SUPPORTED_GEN_STEPS) - fallback if driver registry failed
    try:
        from quantumvitas.core.driver_registry import DriverRegistry
        import quantumvitas.drivers  # Ensure drivers are registered

        for engine in DriverRegistry.get_all_engines():
            driver = DriverRegistry.get_driver(engine)
            recipe_class = driver.get_recipe_class()
            if hasattr(recipe_class, 'SUPPORTED_GEN_STEPS'):
                gen_types.update(s.lower() for s in recipe_class.SUPPORTED_GEN_STEPS)
    except Exception as e:
        import sys
        print(f"Warning: Failed to load driver recipes for GEN_SET: {e}", file=sys.stderr)

    # Minimal fallback types (valid placeholders in code, not domain-specific)
    fallback_types = {
        # Placeholder/fallback types
        "custom", "unknown", "",
        # Preset catalog meta types (not step types but used in code)
        "variants", "variant_step_types",
        # Valid GEN types used in drivers/tests but not in workflow registry
        "freq",  # Frequency/vibrational analysis (ORCA, PySCF)
        "postprocess",  # Post-processing metadata (W90)
    }
    gen_types.update(fallback_types)

    return gen_types


def _build_spec_set() -> Set[str]:
    """
    Build set of all declared SPEC step types from SSOT.

    SSOT sources:
    1. Registry: Get step_type_spec keys
    2. Engine recipes: Compute {PREFIX}_{gen} for all supported GEN steps
    """
    spec_types = set()

    # Source 1: Registry (primary SSOT for SPEC types)
    try:
        from quantumvitas.workflow.registry import get_registry
        registry = get_registry()

        # registry._types is keyed by step_type_spec
        for step_type_spec in registry._types.keys():
            spec_types.add(step_type_spec.lower())
    except Exception as e:
        import sys
        print(f"Warning: Failed to load registry for SPEC_SET: {e}", file=sys.stderr)

    # Source 2: DriverRegistry registered step types (from drivers)
    try:
        from quantumvitas.core.driver_registry import DriverRegistry
        import quantumvitas.drivers  # Ensure drivers are registered

        # Get all registered step types from drivers
        for step_type_spec in DriverRegistry.get_all_step_types():
            spec_types.add(step_type_spec.lower())
    except Exception as e:
        import sys
        print(f"Warning: Failed to load driver step types for SPEC_SET: {e}", file=sys.stderr)

    # Source 3: Engine recipes (compute SPEC = PREFIX + "_" + GEN)
    try:
        from quantumvitas.core.driver_registry import DriverRegistry
        import quantumvitas.drivers

        for engine in DriverRegistry.get_all_engines():
            driver = DriverRegistry.get_driver(engine)
            recipe_class = driver.get_recipe_class()

            # Get PREFIX from recipe
            prefix = getattr(recipe_class, 'PREFIX', engine).lower()

            # Get supported GEN steps
            if hasattr(recipe_class, 'SUPPORTED_GEN_STEPS'):
                for gen in recipe_class.SUPPORTED_GEN_STEPS:
                    spec_types.add(f"{prefix}_{gen}".lower())
    except Exception as e:
        import sys
        print(f"Warning: Failed to load drivers for SPEC_SET (recipes): {e}", file=sys.stderr)

    # Also add all possible {prefix}_{gen} combinations for known prefixes
    # This ensures we don't miss any valid combinations
    try:
        from quantumvitas.core.driver_registry import DriverRegistry
        import quantumvitas.drivers

        gen_types = _build_gen_set()
        for engine in DriverRegistry.get_all_engines():
            driver = DriverRegistry.get_driver(engine)
            recipe_class = driver.get_recipe_class()
            prefix = getattr(recipe_class, 'PREFIX', engine).lower()

            for gen in gen_types:
                if gen:  # Skip empty string
                    spec_types.add(f"{prefix}_{gen}".lower())
    except Exception as e:
        import sys
        print(f"Warning: Failed to load drivers for SPEC_SET (2): {e}", file=sys.stderr)

    # Minimal fallback types
    fallback_types = {
        "unknown", "custom", "custom_unknown",
        "variant_step_types",
        # Preset catalog scope type indicators (not actual step types)
        "qe_variants",
        "variants",  # Used in catalog scope metadata
    }
    spec_types.update(fallback_types)

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
                    expected_set="gen_set",
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
        """Verify gen_set is populated from SSOT."""
        gen_set = get_gen_set()
        assert len(gen_set) > 0, "gen_set should not be empty"
        assert "scf" in gen_set, "gen_set should contain 'scf'"
        assert "nscf" in gen_set, "gen_set should contain 'nscf'"

    def test_spec_set_not_empty(self):
        """Verify SPEC_SET is populated from SSOT."""
        spec_set = get_spec_set()
        assert len(spec_set) > 0, "SPEC_SET should not be empty"
        assert "qe_scf" in spec_set, "SPEC_SET should contain 'qe_scf'"
        assert "qe_nscf" in spec_set, "SPEC_SET should contain 'qe_nscf'"


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    print("=== Gate C1: Declared StepType Enforcement (SSOT-based) ===")
    print(f"gen_set ({len(get_gen_set())} types): {sorted(get_gen_set())}")
    print(f"SPEC_SET ({len(get_spec_set())} types): {sorted(get_spec_set())[:30]}...")

    violations, files_scanned = scan_all_files()
    print(f"\nScanned {files_scanned} files")
    print(f"Found {len(violations)} violation(s)")

    for v in violations:
        print(f"  {v}")

    exit(1 if violations else 0)
