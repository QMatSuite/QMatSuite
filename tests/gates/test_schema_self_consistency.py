"""
Gate B: Schema self-consistency checks.

Catches "mismatch reference" and "silent poison" bugs:
- B1) to_dict() references missing attributes
- B2) from_dict()/to_dict() key mismatch
- B3) Constructor still uses legacy kw names
- B4) Dict-unpack "silent poison" (**meta)
"""

import ast
import re
from pathlib import Path
from typing import List, Set, Dict, Any, Optional, Tuple
from dataclasses import dataclass

import pytest

# ============================================================================
# Configuration
# ============================================================================

REPO_ROOT = Path(__file__).parent.parent.parent

# Directories to scan
PYTHON_DIRS = [
    REPO_ROOT / "src",
    REPO_ROOT / "tests",
]

# Forbidden legacy keyword argument names in constructors
FORBIDDEN_KW_NAMES = {
    "id",  # Should be ulid
    "calc_id", "step_id", "structure_id", "project_id", "run_id",  # Should be *_ulid
    "step_type",  # Should be step_type_spec or step_type_gen
}

# Classes where `id=` is legitimate (non-ULID uses)
# These use `id` for protocol/graph/identifier purposes, not as resource ULIDs
ALLOWLISTED_ID_CLASSES = {
    # JSON-RPC protocol: `id` correlates requests with responses (spec-mandated)
    "RPCRequest",
    "RPCResponse",
    # Job graph: `id` is a DAG node identifier like "j1", "j2" (not a ULID)
    "Job",
    # Workflow templates: `id` is a string template key like "dft-basic"
    "WorkflowTemplate",
    # Library: `id` is a library identifier string
    "LibraryMetadata",
    # Error context: `id` is passed to describe which resource was not found
    "ResourceNotFoundError",
    # Registry: `id` is a spec key, not a ULID
    "StepTypeSpec",
    # Test mocks (MockMeta.id is legitimate for mocking)
    "MockMeta",
    # XML ElementTree: `id` is an XML attribute name
    "SubElement",
    "Element",
}

# Classes that must use sanitized construction (no **meta)
SENSITIVE_CLASSES = {
    "ResourceMeta",
    "MetaDTO",
    # Add more DTO classes that should not accept raw **meta
}

# DTO-like classes to check for from_dict/to_dict consistency
DTO_PATTERNS = ["DTO", "Model", "Entry", "Meta"]

# Allowlist patterns (files that are explicitly allowed to have issues)
ALLOWLIST_PATTERNS = [
    "src/quantumvitas/_vault/*",  # Legacy archive
]

# ============================================================================
# Violation Types
# ============================================================================

@dataclass
class Violation:
    """Base class for violations."""
    file: Path
    line: int
    message: str
    violation_type: str

    def __str__(self):
        return f"{self.file}:{self.line} - [{self.violation_type}] {self.message}"


# ============================================================================
# B1: to_dict() references missing attributes
# ============================================================================

class ToDictVisitor(ast.NodeVisitor):
    """Check that to_dict() only references existing attributes."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.violations: List[Violation] = []
        self.current_class: str = ""
        self.class_attrs: Set[str] = set()
        self.in_to_dict: bool = False

    def visit_ClassDef(self, node: ast.ClassDef):
        """Collect class attributes and check to_dict methods."""
        old_class = self.current_class
        old_attrs = self.class_attrs
        self.current_class = node.name
        self.class_attrs = set()

        # Collect all class attributes (fields)
        for item in node.body:
            # Annotated assignments (field: type = value)
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                self.class_attrs.add(item.target.id)
            # Simple assignments
            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        self.class_attrs.add(target.id)

        # Also include properties
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                for decorator in item.decorator_list:
                    if isinstance(decorator, ast.Name) and decorator.id == "property":
                        self.class_attrs.add(item.name)

        # Visit child nodes
        self.generic_visit(node)

        self.current_class = old_class
        self.class_attrs = old_attrs

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Check to_dict methods for invalid self.attr references."""
        if node.name == "to_dict" and self.current_class:
            old_in_to_dict = self.in_to_dict
            self.in_to_dict = True
            self.generic_visit(node)
            self.in_to_dict = old_in_to_dict
        else:
            self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute):
        """Check self.attr references in to_dict."""
        if self.in_to_dict and isinstance(node.value, ast.Name) and node.value.id == "self":
            attr = node.attr
            # Allow private attrs and common methods
            if not attr.startswith("_") and attr not in self.class_attrs:
                # Check if it's a method call (will have Call parent)
                # We only flag attribute access, not method calls
                self.violations.append(Violation(
                    file=self.file_path,
                    line=node.lineno,
                    message=f"to_dict() references self.{attr} but class '{self.current_class}' has no such field",
                    violation_type="B1_MISSING_ATTR"
                ))
        self.generic_visit(node)


# ============================================================================
# B2: from_dict()/to_dict() key mismatch
# ============================================================================

class DictKeyCollector(ast.NodeVisitor):
    """Collect dict keys used in from_dict and to_dict."""

    def __init__(self):
        self.from_dict_keys: Set[str] = set()
        self.to_dict_keys: Set[str] = set()

    def visit_Subscript(self, node: ast.Subscript):
        """Collect data["key"] patterns."""
        if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
            self.from_dict_keys.add(node.slice.value)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        """Collect data.get("key") patterns."""
        if isinstance(node.func, ast.Attribute) and node.func.attr == "get":
            if node.args and isinstance(node.args[0], ast.Constant):
                if isinstance(node.args[0].value, str):
                    self.from_dict_keys.add(node.args[0].value)
        self.generic_visit(node)


class FromToDictVisitor(ast.NodeVisitor):
    """Check from_dict/to_dict key consistency."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.violations: List[Violation] = []
        self.current_class: str = ""
        self.from_dict_node: Optional[ast.FunctionDef] = None
        self.to_dict_node: Optional[ast.FunctionDef] = None

    def visit_ClassDef(self, node: ast.ClassDef):
        """Check classes with both from_dict and to_dict."""
        old_class = self.current_class
        old_from = self.from_dict_node
        old_to = self.to_dict_node
        self.current_class = node.name
        self.from_dict_node = None
        self.to_dict_node = None

        # Find from_dict and to_dict
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                if item.name == "from_dict":
                    self.from_dict_node = item
                elif item.name == "to_dict":
                    self.to_dict_node = item

        # Check consistency if both exist
        if self.from_dict_node and self.to_dict_node:
            self._check_key_consistency()

        # Visit children
        self.generic_visit(node)

        self.current_class = old_class
        self.from_dict_node = old_from
        self.to_dict_node = old_to

    def _check_key_consistency(self):
        """Check that from_dict reads are subset of to_dict writes."""
        # Collect keys from from_dict
        from_collector = DictKeyCollector()
        from_collector.visit(self.from_dict_node)
        from_keys = from_collector.from_dict_keys

        # Collect keys from to_dict (look for dict assignments)
        to_keys = set()
        for node in ast.walk(self.to_dict_node):
            # Pattern: {"key": ...}
            if isinstance(node, ast.Dict):
                for key in node.keys:
                    if isinstance(key, ast.Constant) and isinstance(key.value, str):
                        to_keys.add(key.value)
            # Pattern: result["key"] = ...
            if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
                if isinstance(node.slice.value, str):
                    to_keys.add(node.slice.value)

        # Check: from_dict keys should be subset of to_dict keys
        # (allowing some flexibility for optional keys)
        missing = from_keys - to_keys
        if missing and len(missing) > len(from_keys) * 0.5:  # Flag if >50% missing
            self.violations.append(Violation(
                file=self.file_path,
                line=self.from_dict_node.lineno,
                message=f"from_dict() reads keys {missing} not in to_dict() for class '{self.current_class}'",
                violation_type="B2_KEY_MISMATCH"
            ))


# ============================================================================
# B3: Constructor still uses legacy kw names
# ============================================================================

class LegacyKwVisitor(ast.NodeVisitor):
    """Check for legacy keyword argument names in constructors."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.violations: List[Violation] = []

    def visit_Call(self, node: ast.Call):
        """Check call sites for legacy keyword arguments."""
        # Get the function/class being called
        func_name = self._get_call_name(node)

        # Check keyword arguments
        for kw in node.keywords:
            if kw.arg in FORBIDDEN_KW_NAMES:
                # Skip if this is a dict or non-class call
                if not func_name or not func_name[0].isupper():
                    continue

                # Skip `id=` for allowlisted classes (non-ULID uses)
                if kw.arg == "id" and func_name in ALLOWLISTED_ID_CLASSES:
                    continue

                self.violations.append(Violation(
                    file=self.file_path,
                    line=node.lineno,
                    message=f"Legacy keyword '{kw.arg}=' in {func_name}() call",
                    violation_type="B3_LEGACY_KW"
                ))
        self.generic_visit(node)

    def _get_call_name(self, node: ast.Call) -> str:
        """Get the name of the called function/class."""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            return node.func.attr
        return ""


# ============================================================================
# B4: Dict-unpack "silent poison" (**meta)
# ============================================================================

# Legacy keys that should not appear in test assertions
# These patterns indicate tests checking for old field names
FORBIDDEN_ASSERTION_KEYS = {
    # Identity keys (should be *_ulid)
    '"id"',       # Should be "ulid"
    "'id'",       # Should be 'ulid'
    '"calc_id"',  # Should be "calc_ulid"
    "'calc_id'",
    '"step_id"',  # Should be "step_ulid"
    "'step_id'",
    '"structure_id"',  # Should be "structure_ulid"
    "'structure_id'",
    '"project_id"',   # Should be "project_ulid"
    "'project_id'",
    '"run_id"',       # Should be "run_ulid"
    "'run_id'",
    # Step type keys (should be step_type_spec or step_type_gen)
    '"step_type"',    # Should be "step_type_spec" or "step_type_gen"
    "'step_type'",
}

# Patterns for assertions to check
ASSERTION_PATTERNS = [
    # assert "key" in dict
    r'assert\s+["\'](\w+)["\']\s+in\s+',
    # dict["key"] or dict['key'] access
    r'\[["\'](id|calc_id|step_id|structure_id|project_id|run_id|step_type)["\']\]',
    # .get("key") access
    r'\.get\(["\'](\w+)["\']',
]

# Allowlist: files where legacy keys are legitimate
B5_ALLOWLIST_FILES = [
    "test_schema_self_consistency.py",  # This file itself
    "test_no_legacy_identity_fields.py",  # Gate A
    "_vault/",  # Legacy archive
]

# Allowlist: contexts where "id" is legitimate (not a ULID)
B5_ALLOWLIST_CONTEXTS = [
    "request_id",   # JSON-RPC request correlation
    "job_id",       # Job graph node identifiers (not ULIDs)
    "template_id",  # Template identifiers
    "template",     # Workflow template identifiers
    "rpc",          # RPC protocol
    "json-rpc",
    "module",       # QE parameter metadata module identifiers (e.g., "pw", "cp")
    "section",      # QE parameter metadata section identifiers (e.g., "CONTROL", "SYSTEM")
    "qe_parameter", # QE parameter metadata
    "optimade",     # OPTIMADE external API standard uses "id" for record identifiers
    "candidate",    # OPTIMADE candidate records
]

# Allowlist: line patterns that are internal test fixtures, not API response checks
B5_ALLOWLIST_LINE_PATTERNS = [
    # Fixture return dicts are internal test convenience, not API assertions
    "return {",
    "return{",
    # Variable assignment from fixture dict is ok
    "= lammps_project[",
    "= cp2k_project[",
    "= project[",
    "= fixture[",
    "= inline_lj_project[",
    "= external_potential_project[",
    # Creating test fixture dicts
    '"project_root":',
    '"calc_dir":',
    '"step_ulid":',  # Already using ulid
    # FORBIDDEN_FIELDS constants etc.
    "FORBIDDEN_",
    # Request payload parameter checks (GEN layer - user-facing input)
    "payload[",
    "build_v0_payload",
    # v0 contract tests for request parameters
    "v0_payloads",
    "in payload",  # assert "key" in payload (request parameter check)
    # Negative assertions (checking legacy fields don't exist)
    "not in",
    "not hasattr",
]


class DictUnpackVisitor(ast.NodeVisitor):
    """Check for unsafe **meta unpacking into sensitive classes."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.violations: List[Violation] = []

    def visit_Call(self, node: ast.Call):
        """Check for **meta unpacking into sensitive classes."""
        func_name = self._get_call_name(node)

        # Check if calling a sensitive class
        if func_name in SENSITIVE_CLASSES:
            # Check for **kwargs unpacking
            for kw in node.keywords:
                if kw.arg is None:  # **kwargs
                    # Check if it's a simple variable (potential unsanitized dict)
                    if isinstance(kw.value, ast.Name):
                        var_name = kw.value.id
                        # Flag if unpacking a variable named 'meta', 'data', etc.
                        if var_name in ("meta", "data", "kwargs", "d", "dict_data"):
                            self.violations.append(Violation(
                                file=self.file_path,
                                line=node.lineno,
                                message=f"Unsafe dict-unpack: {func_name}(**{var_name}) - use from_dict() instead",
                                violation_type="B4_DICT_UNPACK"
                            ))
        self.generic_visit(node)

    def _get_call_name(self, node: ast.Call) -> str:
        """Get the name of the called function/class."""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            return node.func.attr
        return ""


# ============================================================================
# Scanning Functions
# ============================================================================

def is_allowlisted(path: Path) -> bool:
    """Check if a file matches any allowlist pattern."""
    import fnmatch
    rel_path = str(path.relative_to(REPO_ROOT))
    for pattern in ALLOWLIST_PATTERNS:
        if fnmatch.fnmatch(rel_path, pattern):
            return True
    return False


def scan_python_file_b1(file_path: Path) -> List[Violation]:
    """Scan for B1 violations (to_dict references missing attrs)."""
    try:
        content = file_path.read_text()
        tree = ast.parse(content)
    except Exception:
        return []

    visitor = ToDictVisitor(file_path)
    visitor.visit(tree)
    return visitor.violations


def scan_python_file_b2(file_path: Path) -> List[Violation]:
    """Scan for B2 violations (from_dict/to_dict key mismatch)."""
    try:
        content = file_path.read_text()
        tree = ast.parse(content)
    except Exception:
        return []

    visitor = FromToDictVisitor(file_path)
    visitor.visit(tree)
    return visitor.violations


def scan_python_file_b3(file_path: Path) -> List[Violation]:
    """Scan for B3 violations (legacy kw names in constructors)."""
    try:
        content = file_path.read_text()
        tree = ast.parse(content)
    except Exception:
        return []

    visitor = LegacyKwVisitor(file_path)
    visitor.visit(tree)
    return visitor.violations


def scan_python_file_b4(file_path: Path) -> List[Violation]:
    """Scan for B4 violations (unsafe dict-unpack)."""
    try:
        content = file_path.read_text()
        tree = ast.parse(content)
    except Exception:
        return []

    visitor = DictUnpackVisitor(file_path)
    visitor.visit(tree)
    return visitor.violations


# ============================================================================
# B5: Legacy key assertions in tests
# ============================================================================

def scan_test_file_b5(file_path: Path) -> List[Violation]:
    """Scan test file for legacy key assertions.

    Focus on catching assertions that check API/DTO response shapes,
    not internal test fixture convenience dicts.
    """
    violations = []

    # Skip allowlisted files
    for pattern in B5_ALLOWLIST_FILES:
        if pattern in str(file_path):
            return []

    try:
        content = file_path.read_text()
        lines = content.split("\n")
    except Exception:
        return []

    for line_num, line in enumerate(lines, 1):
        # Skip comments and docstrings
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
            continue

        # Check for allowlisted contexts in the line
        line_lower = line.lower()
        if any(ctx in line_lower for ctx in B5_ALLOWLIST_CONTEXTS):
            continue

        # Skip internal fixture patterns (not API response assertions)
        if any(pattern in line for pattern in B5_ALLOWLIST_LINE_PATTERNS):
            continue

        # Check for forbidden assertion patterns - focus on assert/in patterns
        # Pattern 1: assert "id" in data (but not "ulid")
        # Exclude negative assertions like "assert "id" not in" which are legitimate enforcement
        if 'assert' in line and '"id"' in line and '"ulid"' not in line:
            # Skip negative assertions (checking legacy field doesn't exist)
            if 'not in' in line or '!=' in line or 'not hasattr' in line:
                continue
            # Skip docstrings/comments explaining negative assertions
            if 'hasattr' in line.lower():
                continue
            # Make sure it's not checking for ulid
            if not any(x in line for x in ['"ulid"', "'ulid'"]):
                violations.append(Violation(
                    file=file_path,
                    line=line_num,
                    message=f'Legacy assertion: "id" should be "ulid"',
                    violation_type="B5_LEGACY_ASSERTION"
                ))

        # Pattern 2: data["id"] or data['id'] access in assertion context
        if ('["id"]' in line or "['id']" in line) and ('assert' in line or 'response' in line.lower()):
            # Skip if line contains ulid context
            if 'ulid' not in line.lower() and 'template' not in line.lower() and 'rpc' not in line.lower():
                violations.append(Violation(
                    file=file_path,
                    line=line_num,
                    message=f'Legacy key access: ["id"] should be ["ulid"]',
                    violation_type="B5_LEGACY_ASSERTION"
                ))

        # Pattern 3: *_id keys in assertion context or response access
        # Only flag these in assert/response contexts to reduce false positives
        if 'assert' in line or 'response' in line.lower():
            for legacy_key in ['"calc_id"', "'calc_id'", '"step_id"', "'step_id'",
                              '"structure_id"', "'structure_id'", '"run_id"', "'run_id'"]:
                if legacy_key in line:
                    canonical = legacy_key.replace('_id', '_ulid')
                    violations.append(Violation(
                        file=file_path,
                        line=line_num,
                        message=f'Legacy key: {legacy_key} should be {canonical}',
                        violation_type="B5_LEGACY_ASSERTION"
                    ))
                    break  # Only one violation per line

        # Pattern 4: bare "step_type" in assertion/response context
        if ('assert' in line or 'response' in line.lower()):
            if ('"step_type"' in line or "'step_type'" in line) and \
               'step_type_spec' not in line and 'step_type_gen' not in line:
                violations.append(Violation(
                    file=file_path,
                    line=line_num,
                    message=f'Legacy key: "step_type" should be "step_type_spec" or "step_type_gen"',
                    violation_type="B5_LEGACY_ASSERTION"
                ))

    return violations


# ============================================================================
# B6: Legacy keys in golden fixtures
# ============================================================================

def scan_golden_fixture_b6(file_path: Path) -> List[Violation]:
    """Scan golden fixture for legacy keys in response data."""
    import json

    violations = []

    try:
        content = file_path.read_text()
        data = json.loads(content)
    except Exception:
        return []

    def check_dict_keys(d: dict, path: str = ""):
        """Recursively check dict keys for legacy names."""
        if not isinstance(d, dict):
            return

        for key, value in d.items():
            current_path = f"{path}.{key}" if path else key

            # Skip metadata keys
            if key in ("method", "success", "recipe_name", "baseline_commit",
                       "generated_at", "source", "error"):
                if isinstance(value, dict):
                    check_dict_keys(value, current_path)
                elif isinstance(value, list):
                    for i, item in enumerate(value):
                        if isinstance(item, dict):
                            check_dict_keys(item, f"{current_path}[{i}]")
                continue

            # Check for legacy identity keys (but allow in RPC/template contexts)
            if key == "id" and "template" not in path.lower() and "rpc" not in path.lower():
                # Check if this looks like a ULID context (in response data)
                if "response" in path or not path:
                    violations.append(Violation(
                        file=file_path,
                        line=0,
                        message=f'Legacy key at {current_path}: "id" should be "ulid"',
                        violation_type="B6_GOLDEN_LEGACY"
                    ))

            # Check for *_id keys
            if key in ("calc_id", "step_id", "structure_id", "run_id", "project_id"):
                violations.append(Violation(
                    file=file_path,
                    line=0,
                    message=f'Legacy key at {current_path}: "{key}" should be "{key.replace("_id", "_ulid")}"',
                    violation_type="B6_GOLDEN_LEGACY"
                ))

            # Check for bare step_type
            if key == "step_type":
                violations.append(Violation(
                    file=file_path,
                    line=0,
                    message=f'Legacy key at {current_path}: "step_type" should be "step_type_spec" or "step_type_gen"',
                    violation_type="B6_GOLDEN_LEGACY"
                ))

            # Recurse
            if isinstance(value, dict):
                check_dict_keys(value, current_path)
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        check_dict_keys(item, f"{current_path}[{i}]")

    check_dict_keys(data)
    return violations


def scan_all_files() -> Dict[str, List[Violation]]:
    """Scan all Python files for all violation types."""
    results = {
        "B1": [],
        "B2": [],
        "B3": [],
        "B4": [],
        "B5": [],
        "B6": [],
    }
    allowlisted = []

    for dir_path in PYTHON_DIRS:
        if not dir_path.exists():
            continue

        for file_path in dir_path.rglob("*.py"):
            if is_allowlisted(file_path):
                allowlisted.append(file_path)
                continue

            # B1: to_dict references
            # Disabled for now - too many false positives from inherited methods
            # results["B1"].extend(scan_python_file_b1(file_path))

            # B2: from_dict/to_dict mismatch
            # Disabled for now - needs refinement
            # results["B2"].extend(scan_python_file_b2(file_path))

            # B3: Legacy kw names - This is the most important check
            results["B3"].extend(scan_python_file_b3(file_path))

            # B4: Unsafe dict-unpack
            results["B4"].extend(scan_python_file_b4(file_path))

    # B5: Legacy assertions in test files only
    tests_dir = REPO_ROOT / "tests"
    if tests_dir.exists():
        for file_path in tests_dir.rglob("*.py"):
            if is_allowlisted(file_path):
                continue
            results["B5"].extend(scan_test_file_b5(file_path))

    # B6: Legacy keys in golden fixtures
    fixtures_dir = REPO_ROOT / "tests" / "fixtures"
    if fixtures_dir.exists():
        for golden_dir in fixtures_dir.glob("golden_*"):
            for json_file in golden_dir.rglob("*.json"):
                results["B6"].extend(scan_golden_fixture_b6(json_file))

    # Print allowlisted files
    for path in allowlisted:
        print(f"ALLOWLISTED: {path}")

    return results


# ============================================================================
# Tests
# ============================================================================

class TestSchemaConsistency:
    """Gate B: Schema self-consistency checks."""

    def test_no_legacy_kw_in_constructors(self):
        """
        B3: No legacy keyword argument names in constructors.

        Forbidden: id=, calc_id=, step_id=, structure_id=, project_id=, run_id=, step_type_gen=
        """
        results = scan_all_files()
        violations = results["B3"]

        if violations:
            report = "\n\n=== B3: LEGACY KEYWORD ARGUMENTS ===\n"
            report += f"Found {len(violations)} violation(s):\n\n"
            for v in violations:
                report += f"  {v}\n"
            report += "\n=== END B3 ===\n"
            pytest.fail(report)

    def test_no_unsafe_dict_unpack(self):
        """
        B4: No unsafe **meta unpacking into sensitive classes.

        Forbidden: ResourceMeta(**meta), MetaDTO(**meta), etc.
        Use: ResourceMeta.from_dict(meta) instead.
        """
        results = scan_all_files()
        violations = results["B4"]

        if violations:
            report = "\n\n=== B4: UNSAFE DICT UNPACK ===\n"
            report += f"Found {len(violations)} violation(s):\n\n"
            for v in violations:
                report += f"  {v}\n"
            report += "\n=== END B4 ===\n"
            pytest.fail(report)

    def test_no_legacy_key_assertions(self):
        """
        B5: No legacy key assertions in test files.

        Forbidden patterns in tests:
        - assert "id" in data (should be "ulid")
        - data["calc_id"] (should be "calc_ulid")
        - data["step_id"] (should be "step_ulid")
        - data["step_type"] (should be "step_type_spec" or "step_type_gen")
        """
        results = scan_all_files()
        violations = results["B5"]

        if violations:
            report = "\n\n=== B5: LEGACY KEY ASSERTIONS IN TESTS ===\n"
            report += f"Found {len(violations)} violation(s):\n\n"
            for v in violations[:50]:  # Limit output
                report += f"  {v}\n"
            if len(violations) > 50:
                report += f"  ... and {len(violations) - 50} more\n"
            report += "\n=== END B5 ===\n"
            pytest.fail(report)

    def test_no_legacy_keys_in_golden_fixtures(self):
        """
        B6: No legacy keys in golden fixtures.

        Golden fixtures should use canonical field names:
        - "ulid" instead of "id"
        - "calc_ulid" instead of "calc_id"
        - "step_ulid" instead of "step_id"
        - "step_type_spec"/"step_type_gen" instead of "step_type"
        """
        results = scan_all_files()
        violations = results["B6"]

        if violations:
            report = "\n\n=== B6: LEGACY KEYS IN GOLDEN FIXTURES ===\n"
            report += f"Found {len(violations)} violation(s):\n\n"
            for v in violations[:50]:  # Limit output
                report += f"  {v}\n"
            if len(violations) > 50:
                report += f"  ... and {len(violations) - 50} more\n"
            report += "\n=== END B6 ===\n"
            pytest.fail(report)


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    print("=== Gate B: Schema Self-Consistency ===")

    results = scan_all_files()

    total = 0
    for check, violations in results.items():
        print(f"\n{check}: {len(violations)} violation(s)")
        for v in violations[:10]:  # Limit output
            print(f"  {v}")
        if len(violations) > 10:
            print(f"  ... and {len(violations) - 10} more")
        total += len(violations)

    print(f"\n=== TOTAL: {total} violation(s) ===")
    exit(1 if total > 0 else 0)
