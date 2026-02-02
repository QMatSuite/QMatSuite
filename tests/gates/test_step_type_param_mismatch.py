"""
Gate C3: Step Type Parameter/Argument Mismatch Detection

This gate detects when a function's parameter type doesn't match the argument type:
- Function expects step_type_gen but is called with step_type_spec argument
- Function expects step_type_spec but is called with step_type_gen argument

The layering rules:
- UI/Preset/Workflow/Registry layer: step_type_gen ONLY
- YAML/Runner/Execution/Engine layer: step_type_spec ONLY

This gate catches violations where the CALLER passes a wrong-typed variable.
"""

import ast
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent

SCAN_DIRS = [
    REPO_ROOT / "src",
    REPO_ROOT / "tests",
]

# Files to skip
ALLOWLIST_PATTERNS = [
    "src/quantumvitas/_vault/*",  # Legacy archive
    "tests/gates/test_step_type_param_mismatch.py",  # This file itself
]

# Known functions and their expected parameter types
# Format: "module.function": {"param_name": "gen" | "spec"}
# These are the key functions where type matters
KNOWN_FUNCTION_SIGNATURES: Dict[str, Dict[str, str]] = {
    # Registry functions - expect GEN types
    "registry.get": {"step_type_gen": "gen"},
    "registry.has": {"step_type_gen": "gen"},
    "get_registry().get": {"step_type_gen": "gen"},
    "get_registry().has": {"step_type_gen": "gen"},

    # Driver registry - expects SPEC for is_step_type_registered
    "DriverRegistry.is_step_type_registered": {"step_type_spec": "spec"},
    "DriverRegistry.get_engine_for_step_type": {"step_type_spec": "spec"},
    "DriverRegistry.get_step_type_spec": {"step_type_spec": "spec"},

    # Conversion functions
    "gen_from": {"step_type_spec": "spec"},  # Input is SPEC, outputs GEN
    "spec_from": {"step_type_gen": "gen"},  # Input is GEN, outputs SPEC
    # Note: is_spec is not checked - it's a format-checking function

    # Factory functions - expect GEN
    "create_step_doc": {"step_type_gen": "gen"},
    "create_and_save_step": {"step_type_gen": "gen"},

    # Service layer - expects GEN (UI layer)
    "add_step": {"step_type_gen": "gen"},
    "svc.calculation.add_step": {"step_type_gen": "gen"},
}


@dataclass
class Violation:
    """Represents a parameter/argument type mismatch."""
    file: Path
    line: int
    func_name: str
    param_name: str
    expected_type: str  # "gen" or "spec"
    actual_var: str  # Variable name used
    actual_type: str  # "gen" or "spec" (inferred from var name)

    def __str__(self):
        return (
            f"{self.file}:{self.line} - "
            f"{self.func_name}({self.param_name}=...) expects {self.expected_type.upper()} "
            f"but called with '{self.actual_var}' (looks like {self.actual_type.upper()})"
        )


def infer_type_from_name(var_name: str) -> Optional[str]:
    """Infer GEN or SPEC type from variable name.

    Returns:
        "gen" if name suggests GEN type
        "spec" if name suggests SPEC type
        None if cannot determine
    """
    name_lower = var_name.lower()

    # Check for explicit type suffixes
    if "_gen" in name_lower or name_lower.endswith("_gen"):
        return "gen"
    if "_spec" in name_lower or name_lower.endswith("_spec"):
        return "spec"

    # Check for full variable names
    if name_lower in ("step_type_gen", "gen_type", "gen_step", "gen_step_type"):
        return "gen"
    if name_lower in ("step_type_spec", "spec_type", "spec_step", "machine_step_type"):
        return "spec"

    # Check for patterns
    if name_lower.startswith("step_type_gen"):
        return "gen"
    if name_lower.startswith("step_type_spec"):
        return "spec"

    return None


def is_allowlisted(path: Path) -> bool:
    """Check if path matches allowlist patterns."""
    import fnmatch
    rel_path = str(path.relative_to(REPO_ROOT))
    for pattern in ALLOWLIST_PATTERNS:
        if fnmatch.fnmatch(rel_path, pattern):
            return True
    return False


class ParamMismatchVisitor(ast.NodeVisitor):
    """AST visitor to find parameter/argument type mismatches."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.violations: List[Violation] = []
        self.current_assignments: Dict[str, str] = {}  # var_name -> inferred type

    def visit_Assign(self, node: ast.Assign):
        """Track variable assignments to infer types."""
        for target in node.targets:
            if isinstance(target, ast.Name):
                inferred = infer_type_from_name(target.id)
                if inferred:
                    self.current_assignments[target.id] = inferred
        self.generic_visit(node)

    def _get_func_name(self, node: ast.Call) -> str:
        """Extract function name from call node."""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                return f"{node.func.value.id}.{node.func.attr}"
            elif isinstance(node.func.value, ast.Call):
                # Handle cases like get_registry().get()
                inner_name = self._get_func_name(node.func.value)
                return f"{inner_name}().{node.func.attr}"
            elif isinstance(node.func.value, ast.Attribute):
                # Handle cases like self.registry.get()
                return f"...{node.func.attr}"
        return ""

    def _check_keyword_arg(self, func_name: str, keyword: ast.keyword, lineno: int):
        """Check a keyword argument for type mismatch."""
        if keyword.arg is None:
            return

        # Find matching function signature
        for sig_pattern, params in KNOWN_FUNCTION_SIGNATURES.items():
            if sig_pattern in func_name or func_name.endswith(sig_pattern.split(".")[-1]):
                if keyword.arg in params:
                    expected_type = params[keyword.arg]
                    if expected_type == "any":
                        continue  # No type restriction

                    # Get actual argument type
                    actual_type = None
                    actual_var = None

                    if isinstance(keyword.value, ast.Name):
                        actual_var = keyword.value.id
                        actual_type = infer_type_from_name(actual_var)

                    if actual_type and actual_var and actual_type != expected_type:
                        self.violations.append(Violation(
                            file=self.file_path,
                            line=lineno,
                            func_name=func_name,
                            param_name=keyword.arg,
                            expected_type=expected_type,
                            actual_var=actual_var,
                            actual_type=actual_type,
                        ))

    def _check_positional_arg(self, func_name: str, arg: ast.expr, position: int, lineno: int):
        """Check a positional argument for type mismatch.

        This checks specific known functions where first positional arg has type requirements.
        """
        # registry.get(step_type) - first arg should be GEN
        if func_name.endswith(".get") and "registry" in func_name.lower():
            if position == 0 and isinstance(arg, ast.Name):
                actual_var = arg.id
                actual_type = infer_type_from_name(actual_var)
                if actual_type == "spec":
                    self.violations.append(Violation(
                        file=self.file_path,
                        line=lineno,
                        func_name=func_name,
                        param_name="step_type (positional)",
                        expected_type="gen",
                        actual_var=actual_var,
                        actual_type=actual_type,
                    ))

        # gen_from(spec) - first arg should be SPEC
        if func_name == "gen_from":
            if position == 0 and isinstance(arg, ast.Name):
                actual_var = arg.id
                actual_type = infer_type_from_name(actual_var)
                if actual_type == "gen":
                    self.violations.append(Violation(
                        file=self.file_path,
                        line=lineno,
                        func_name=func_name,
                        param_name="step_type_spec (positional)",
                        expected_type="spec",
                        actual_var=actual_var,
                        actual_type=actual_type,
                    ))

    def visit_Call(self, node: ast.Call):
        """Visit function calls to check argument types."""
        func_name = self._get_func_name(node)

        if func_name:
            # Check keyword arguments
            for keyword in node.keywords:
                self._check_keyword_arg(func_name, keyword, node.lineno)

            # Check positional arguments
            for i, arg in enumerate(node.args):
                self._check_positional_arg(func_name, arg, i, node.lineno)

        self.generic_visit(node)


def scan_python_file(file_path: Path) -> List[Violation]:
    """Scan a Python file for parameter/argument type mismatches."""
    try:
        content = file_path.read_text()
        tree = ast.parse(content)
    except Exception:
        return []

    visitor = ParamMismatchVisitor(file_path)
    visitor.visit(tree)
    return visitor.violations


def scan_all_files() -> Tuple[List[Violation], int]:
    """Scan all Python files and return violations."""
    all_violations = []
    files_scanned = 0

    for scan_dir in SCAN_DIRS:
        if not scan_dir.exists():
            continue

        for file_path in scan_dir.rglob("*.py"):
            if is_allowlisted(file_path):
                continue

            files_scanned += 1
            violations = scan_python_file(file_path)
            all_violations.extend(violations)

    return all_violations, files_scanned


class TestStepTypeParamMismatch:
    """Gate C3: Detect step type parameter/argument mismatches."""

    def test_no_param_mismatches(self):
        """
        Gate C3: Function parameter types must match argument types.

        Detects:
        - registry.get(step_type_spec) where get() expects GEN
        - gen_from(step_type_gen) where gen_from() expects SPEC
        - Similar mismatches for known functions
        """
        violations, files_scanned = scan_all_files()

        if violations:
            report = f"\n\n=== GATE C3: PARAMETER TYPE MISMATCH VIOLATIONS ===\n"
            report += f"Scanned {files_scanned} files\n"
            report += f"Found {len(violations)} violation(s):\n\n"
            for v in violations:
                report += f"  {v}\n"
            report += "\n=== END VIOLATIONS ===\n"
            report += "\nFix: Ensure argument variable type matches parameter type.\n"
            report += "- UI/Preset/Workflow layer uses step_type_gen\n"
            report += "- YAML/Runner/Execution layer uses step_type_spec\n"
            pytest.fail(report)


if __name__ == "__main__":
    print("=== Gate C3: Step Type Parameter/Argument Mismatch Detection ===")
    violations, files_scanned = scan_all_files()
    print(f"Scanned {files_scanned} files")
    print(f"Found {len(violations)} violation(s)")

    for v in violations:
        print(f"  {v}")

    exit(1 if violations else 0)
