"""
Gate C2: step_type_spec/gen Cross-Assignment Lint

Prevents assigning SPEC values into GEN fields (and vice versa) in Python code.

Canonical rule:
- step_type_spec: Engine-prefixed type (e.g., "qe_scf") - SPEC taint
- step_type_gen: Engine-agnostic type (e.g., "scf") - GEN taint

What must fail:
- step_type_gen = step_type_spec  (SPEC → GEN sink)
- step_type_gen = obj.step_type_spec
- payload["step_type_gen"] = step_type_spec
- func(step_type_gen=step_type_spec)
- And vice versa (GEN → SPEC sink)

Taint model:
- Local to each function (no inter-procedural analysis)
- Variables assigned from step_type_spec sources get SPEC taint
- Variables assigned from step_type_gen sources get GEN taint
- Complex expressions → UNKNOWN (conservative)
"""

import ast
from pathlib import Path
from typing import Set, List, Dict, Optional
from enum import Enum, auto
from dataclasses import dataclass

import pytest

# ============================================================================
# Configuration
# ============================================================================

REPO_ROOT = Path(__file__).parent.parent.parent

SCAN_DIRS = [
    REPO_ROOT / "src",
    REPO_ROOT / "tests",
    REPO_ROOT / "tools",
]

# Files to skip
SKIP_PATTERNS = [
    # This gate file itself (contains intentional bad examples for testing)
    "tests/gates/test_step_type_cross_assignment.py",
    # Legacy vault
    "src/qmatsuite/_vault/*",
    # Build artifacts
    "**/build/*",
    "**/.venv/*",
    "**/dist/*",
    "**/__pycache__/*",
    "**/.git/*",
]

# Known intentional cross-assignments (with justification)
# Format: (file_pattern, line_number, justification)
KNOWN_VIOLATIONS = [
    # No known violations - all cross-assignments must be fixed, never allowlisted
]

# ============================================================================
# Taint Model
# ============================================================================

class Taint(Enum):
    UNKNOWN = auto()
    SPEC = auto()  # step_type_spec
    GEN = auto()   # step_type_gen


@dataclass
class Violation:
    """Represents a cross-assignment violation."""
    file: Path
    line: int
    sink_type: str  # "step_type_gen" or "step_type_spec"
    source_taint: Taint
    snippet: str

    def __str__(self):
        taint_name = "SPEC" if self.source_taint == Taint.SPEC else "GEN"
        return f"{self.file}:{self.line} - {taint_name} value assigned to {self.sink_type} sink: {self.snippet}"


# ============================================================================
# AST Taint Analysis
# ============================================================================

class TaintAnalyzer(ast.NodeVisitor):
    """
    Per-function taint analysis for step_type_spec/gen cross-assignment.

    Tracks taint of local variables within a single function scope.
    Does NOT do inter-procedural analysis.
    """

    def __init__(self, file_path: Path, source_lines: List[str]):
        self.file_path = file_path
        self.source_lines = source_lines
        self.violations: List[Violation] = []
        # Per-function taint map (reset on each function entry)
        self.taint_map: Dict[str, Taint] = {}

    def _get_snippet(self, node: ast.AST) -> str:
        """Get source snippet for a node."""
        try:
            lineno = getattr(node, 'lineno', 0)
            if 0 < lineno <= len(self.source_lines):
                line = self.source_lines[lineno - 1].strip()
                # Truncate long lines
                if len(line) > 80:
                    line = line[:77] + "..."
                return line
        except Exception:
            pass
        return "<unknown>"

    def _get_taint_from_expr(self, node: ast.expr) -> Taint:
        """
        Determine taint of an expression.

        Returns SPEC, GEN, or UNKNOWN based on the expression type.
        """
        # Direct name reference
        if isinstance(node, ast.Name):
            name = node.id
            # Check if name itself is canonical
            if name == "step_type_spec":
                return Taint.SPEC
            if name == "step_type_gen":
                return Taint.GEN
            # Check tracked variable taint
            return self.taint_map.get(name, Taint.UNKNOWN)

        # Attribute access: obj.step_type_spec or obj.step_type_gen
        if isinstance(node, ast.Attribute):
            if node.attr == "step_type_spec":
                return Taint.SPEC
            if node.attr == "step_type_gen":
                return Taint.GEN
            return Taint.UNKNOWN

        # Subscript access: d["step_type_spec"] or d["step_type_gen"]
        if isinstance(node, ast.Subscript):
            if isinstance(node.slice, ast.Constant):
                if node.slice.value == "step_type_spec":
                    return Taint.SPEC
                if node.slice.value == "step_type_gen":
                    return Taint.GEN
            return Taint.UNKNOWN

        # Method call: d.get("step_type_spec") or d.get("step_type_gen")
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr == "get":
                if node.args and isinstance(node.args[0], ast.Constant):
                    key = node.args[0].value
                    if key == "step_type_spec":
                        return Taint.SPEC
                    if key == "step_type_gen":
                        return Taint.GEN
            return Taint.UNKNOWN

        # All other expressions: UNKNOWN (conservative)
        return Taint.UNKNOWN

    def _check_sink(self, sink_name: str, value_node: ast.expr, lineno: int) -> None:
        """
        Check if value flows into a sink with wrong taint.

        Args:
            sink_name: "step_type_spec" or "step_type_gen"
            value_node: The RHS expression being assigned
            lineno: Line number for reporting
        """
        value_taint = self._get_taint_from_expr(value_node)

        if value_taint == Taint.UNKNOWN:
            return  # Can't determine, skip

        # Check for cross-assignment
        if sink_name == "step_type_gen" and value_taint == Taint.SPEC:
            self.violations.append(Violation(
                file=self.file_path,
                line=lineno,
                sink_type="step_type_gen",
                source_taint=Taint.SPEC,
                snippet=self._get_snippet(value_node),
            ))
        elif sink_name == "step_type_spec" and value_taint == Taint.GEN:
            self.violations.append(Violation(
                file=self.file_path,
                line=lineno,
                sink_type="step_type_spec",
                source_taint=Taint.GEN,
                snippet=self._get_snippet(value_node),
            ))

    def _update_taint(self, target_name: str, value_node: ast.expr) -> None:
        """Update taint map for an assignment."""
        # If target is canonical name, set its taint
        if target_name == "step_type_spec":
            self.taint_map[target_name] = Taint.SPEC
        elif target_name == "step_type_gen":
            self.taint_map[target_name] = Taint.GEN
        else:
            # Propagate taint from RHS
            value_taint = self._get_taint_from_expr(value_node)
            if value_taint != Taint.UNKNOWN:
                self.taint_map[target_name] = value_taint
            else:
                # Unknown RHS clears any previous taint
                self.taint_map.pop(target_name, None)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Reset taint map on function entry."""
        old_taint_map = self.taint_map
        self.taint_map = {}
        self.generic_visit(node)
        self.taint_map = old_taint_map

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Reset taint map on async function entry."""
        old_taint_map = self.taint_map
        self.taint_map = {}
        self.generic_visit(node)
        self.taint_map = old_taint_map

    def visit_Assign(self, node: ast.Assign) -> None:
        """
        Check assignments:
        - step_type_gen = <SPEC value>  → violation
        - step_type_spec = <GEN value>  → violation
        - x = step_type_spec  → taint x as SPEC
        """
        for target in node.targets:
            # Simple name assignment: x = value
            if isinstance(target, ast.Name):
                target_name = target.id

                # Check if assigning to canonical sink
                if target_name in ("step_type_gen", "step_type_spec"):
                    self._check_sink(target_name, node.value, node.lineno)

                # Update taint for this variable
                self._update_taint(target_name, node.value)

            # Subscript assignment: d["step_type_gen"] = value
            elif isinstance(target, ast.Subscript):
                if isinstance(target.slice, ast.Constant):
                    key = target.slice.value
                    if key in ("step_type_gen", "step_type_spec"):
                        self._check_sink(key, node.value, node.lineno)

            # Attribute assignment: obj.step_type_gen = value
            elif isinstance(target, ast.Attribute):
                if target.attr in ("step_type_gen", "step_type_spec"):
                    self._check_sink(target.attr, node.value, node.lineno)

        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        """Check annotated assignments: x: str = value"""
        if node.value is None:
            self.generic_visit(node)
            return

        target = node.target
        if isinstance(target, ast.Name):
            target_name = target.id
            if target_name in ("step_type_gen", "step_type_spec"):
                self._check_sink(target_name, node.value, node.lineno)
            self._update_taint(target_name, node.value)

        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """
        Check function calls with keyword arguments:
        - func(step_type_gen=<SPEC value>)  → violation
        - func(step_type_spec=<GEN value>)  → violation
        """
        for keyword in node.keywords:
            if keyword.arg in ("step_type_gen", "step_type_spec"):
                self._check_sink(keyword.arg, keyword.value,
                               keyword.lineno if hasattr(keyword, 'lineno') else node.lineno)

        self.generic_visit(node)

    def visit_Dict(self, node: ast.Dict) -> None:
        """
        Check dict literals:
        - {"step_type_gen": <SPEC value>}  → violation
        """
        for key, value in zip(node.keys, node.values):
            if key is None:
                continue
            if isinstance(key, ast.Constant) and key.value in ("step_type_gen", "step_type_spec"):
                self._check_sink(key.value, value,
                               key.lineno if hasattr(key, 'lineno') else node.lineno)

        self.generic_visit(node)


# ============================================================================
# File Scanning
# ============================================================================

def should_skip(path: Path) -> bool:
    """Check if file should be skipped."""
    import fnmatch
    rel_path = str(path.relative_to(REPO_ROOT))
    for pattern in SKIP_PATTERNS:
        if fnmatch.fnmatch(rel_path, pattern):
            return True
    return False


def is_known_violation(violation: Violation) -> bool:
    """Check if violation is in the known allowlist."""
    import fnmatch
    rel_path = str(violation.file.relative_to(REPO_ROOT))
    for file_pattern, line, _justification in KNOWN_VIOLATIONS:
        if fnmatch.fnmatch(rel_path, file_pattern) and violation.line == line:
            return True
    return False


def analyze_file(file_path: Path) -> List[Violation]:
    """Analyze a single Python file for cross-assignment violations."""
    try:
        content = file_path.read_text()
        tree = ast.parse(content)
        source_lines = content.splitlines()
    except Exception:
        return []

    analyzer = TaintAnalyzer(file_path, source_lines)
    analyzer.visit(tree)
    return analyzer.violations


def scan_all_files() -> tuple[List[Violation], int, int]:
    """Scan all Python files and return violations.

    Returns:
        Tuple of (violations, files_scanned, known_violations_skipped)
    """
    all_violations = []
    files_scanned = 0
    known_skipped = 0

    for scan_dir in SCAN_DIRS:
        if not scan_dir.exists():
            continue

        for file_path in scan_dir.rglob("*.py"):
            if should_skip(file_path):
                continue

            files_scanned += 1
            violations = analyze_file(file_path)

            # Filter out known violations
            for v in violations:
                if is_known_violation(v):
                    known_skipped += 1
                else:
                    all_violations.append(v)

    return all_violations, files_scanned, known_skipped


# ============================================================================
# Tests
# ============================================================================

class TestCrossAssignmentGate:
    """Gate C2: Ensure no SPEC→GEN or GEN→SPEC cross-assignments."""

    def test_no_cross_assignments(self):
        """
        Gate C2: All step_type_spec/gen assignments must respect taint.

        Scans src/, tests/, tools/ for:
        - step_type_gen = <SPEC value>  (SPEC → GEN sink)
        - step_type_spec = <GEN value>  (GEN → SPEC sink)

        Where SPEC value is:
        - Variable named step_type_spec
        - Attribute access .step_type_spec
        - Dict access ["step_type_spec"]
        - Variable previously assigned from any of above

        Same logic for GEN.
        """
        violations, files_scanned, known_skipped = scan_all_files()

        if violations:
            report = f"\n\n=== GATE C2: CROSS-ASSIGNMENT VIOLATIONS ===\n"
            report += f"Scanned {files_scanned} files\n"
            report += f"Found {len(violations)} violation(s)"
            if known_skipped:
                report += f" (skipped {known_skipped} known violation(s))"
            report += ":\n\n"
            for v in violations:
                report += f"  {v}\n"
            report += "\n=== END VIOLATIONS ===\n"
            pytest.fail(report)

    def test_gate_catches_spec_to_gen_direct(self):
        """Verify gate catches direct SPEC → GEN assignment."""
        # Inline test snippet
        code = '''
def bad_function():
    step_type_spec = "qe_scf"
    step_type_gen = step_type_spec  # VIOLATION: SPEC → GEN
'''
        tree = ast.parse(code)
        analyzer = TaintAnalyzer(Path("test.py"), code.splitlines())
        analyzer.visit(tree)

        assert len(analyzer.violations) == 1
        assert analyzer.violations[0].sink_type == "step_type_gen"
        assert analyzer.violations[0].source_taint == Taint.SPEC

    def test_gate_catches_gen_to_spec_direct(self):
        """Verify gate catches direct GEN → SPEC assignment."""
        code = '''
def bad_function():
    step_type_gen = "scf"
    step_type_spec = step_type_gen  # VIOLATION: GEN → SPEC
'''
        tree = ast.parse(code)
        analyzer = TaintAnalyzer(Path("test.py"), code.splitlines())
        analyzer.visit(tree)

        assert len(analyzer.violations) == 1
        assert analyzer.violations[0].sink_type == "step_type_spec"
        assert analyzer.violations[0].source_taint == Taint.GEN

    def test_gate_catches_attribute_access(self):
        """Verify gate catches cross-assignment via attribute access."""
        code = '''
def bad_function(obj):
    step_type_gen = obj.step_type_spec  # VIOLATION: .step_type_spec → GEN
'''
        tree = ast.parse(code)
        analyzer = TaintAnalyzer(Path("test.py"), code.splitlines())
        analyzer.visit(tree)

        assert len(analyzer.violations) == 1
        assert analyzer.violations[0].sink_type == "step_type_gen"

    def test_gate_catches_dict_literal(self):
        """Verify gate catches cross-assignment in dict literals."""
        code = '''
def bad_function():
    step_type_spec = "qe_scf"
    data = {"step_type_gen": step_type_spec}  # VIOLATION
'''
        tree = ast.parse(code)
        analyzer = TaintAnalyzer(Path("test.py"), code.splitlines())
        analyzer.visit(tree)

        assert len(analyzer.violations) == 1
        assert analyzer.violations[0].sink_type == "step_type_gen"

    def test_gate_catches_subscript_assignment(self):
        """Verify gate catches cross-assignment via subscript."""
        code = '''
def bad_function():
    step_type_gen = "scf"
    data = {}
    data["step_type_spec"] = step_type_gen  # VIOLATION
'''
        tree = ast.parse(code)
        analyzer = TaintAnalyzer(Path("test.py"), code.splitlines())
        analyzer.visit(tree)

        assert len(analyzer.violations) == 1
        assert analyzer.violations[0].sink_type == "step_type_spec"

    def test_gate_catches_kwarg(self):
        """Verify gate catches cross-assignment via keyword argument."""
        code = '''
def bad_function():
    spec = obj.step_type_spec
    func(step_type_gen=spec)  # VIOLATION: spec is tainted SPEC
'''
        tree = ast.parse(code)
        analyzer = TaintAnalyzer(Path("test.py"), code.splitlines())
        analyzer.visit(tree)

        assert len(analyzer.violations) == 1
        assert analyzer.violations[0].sink_type == "step_type_gen"

    def test_gate_allows_correct_assignments(self):
        """Verify gate allows correct same-taint assignments."""
        code = '''
def good_function():
    step_type_spec = "qe_scf"
    other_spec = step_type_spec  # OK: SPEC → non-sink
    data = {"step_type_spec": step_type_spec}  # OK: SPEC → SPEC

    step_type_gen = "scf"
    other_gen = step_type_gen  # OK: GEN → non-sink
    data2 = {"step_type_gen": step_type_gen}  # OK: GEN → GEN
'''
        tree = ast.parse(code)
        analyzer = TaintAnalyzer(Path("test.py"), code.splitlines())
        analyzer.visit(tree)

        assert len(analyzer.violations) == 0

    def test_gate_allows_unknown_to_sink(self):
        """Verify gate allows UNKNOWN values to sinks (conservative)."""
        code = '''
def good_function():
    value = some_function()  # UNKNOWN taint
    step_type_gen = value  # OK: UNKNOWN → GEN (can't prove wrong)
    step_type_spec = value  # OK: UNKNOWN → SPEC
'''
        tree = ast.parse(code)
        analyzer = TaintAnalyzer(Path("test.py"), code.splitlines())
        analyzer.visit(tree)

        assert len(analyzer.violations) == 0

    def test_taint_propagation(self):
        """Verify taint propagates through intermediate variables."""
        code = '''
def bad_function():
    spec_val = obj.step_type_spec  # spec_val tainted SPEC
    tmp = spec_val  # tmp tainted SPEC
    step_type_gen = tmp  # VIOLATION: SPEC → GEN via tmp
'''
        tree = ast.parse(code)
        analyzer = TaintAnalyzer(Path("test.py"), code.splitlines())
        analyzer.visit(tree)

        assert len(analyzer.violations) == 1

    def test_taint_reset_on_unknown_reassign(self):
        """Verify taint is cleared when reassigned from UNKNOWN."""
        code = '''
def good_function():
    spec_val = obj.step_type_spec  # spec_val tainted SPEC
    spec_val = some_function()  # spec_val now UNKNOWN
    step_type_gen = spec_val  # OK: UNKNOWN → GEN
'''
        tree = ast.parse(code)
        analyzer = TaintAnalyzer(Path("test.py"), code.splitlines())
        analyzer.visit(tree)

        assert len(analyzer.violations) == 0


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    print("=== Gate C2: Cross-Assignment Lint ===")

    violations, files_scanned, known_skipped = scan_all_files()
    print(f"Scanned {files_scanned} files")
    print(f"Found {len(violations)} violation(s)", end="")
    if known_skipped:
        print(f" (skipped {known_skipped} known violation(s))")
    else:
        print()

    for v in violations:
        print(f"  {v}")

    exit(1 if violations else 0)
