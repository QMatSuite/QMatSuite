"""
Gate test to enforce legacy identity field eradication.

LAW: All QMatSuite resource identities must use canonical names:
- Project: project_ulid (or meta.ulid)
- Calculation: calc_ulid (or meta.ulid)
- Step: step_ulid (or meta.ulid)
- Structure: structure_ulid (or meta.ulid)

FORBIDDEN (for QMatSuite resources):
- id (in meta blocks)
- project_id, calc_id, step_id, structure_id
- any *_id used as ULID identity

STEP TYPE LAW:
- step_type_spec OR step_type_gen (explicit)
- Never ambiguous step_type in persisted/DTO/dataclass fields
"""

import ast
import json
import os
import re
from pathlib import Path
from typing import List, Set, Tuple

import pytest
import yaml

# ============================================================================
# Configuration
# ============================================================================

REPO_ROOT = Path(__file__).parent.parent.parent

# Directories to scan for YAML/JSON resources
RESOURCE_DIRS = [
    REPO_ROOT / "src" / "quantumvitas" / "resources",
    REPO_ROOT / "tests" / "fixtures",
    REPO_ROOT / "tests" / "data",
]

# Directories to scan for Python source
PYTHON_DIRS = [
    REPO_ROOT / "src",
]

# Allowlist: files that are explicitly allowed to have legacy fields
# Format: relative path from REPO_ROOT
ALLOWLIST_PATTERNS = [
    # External schema files
    "tests/fixtures/external_*",
    # Third-party vendored data
    "src/quantumvitas/resources/third_party/*",
    # _vault is legacy archive (explicitly preserved for reference)
    "src/quantumvitas/_vault/*",
]

# Forbidden identity keys in meta blocks (YAML/JSON)
FORBIDDEN_META_KEYS = {"id"}

# Forbidden identity keys anywhere in QMatSuite resources
FORBIDDEN_RESOURCE_ID_KEYS = {
    "project_id", "calc_id", "step_id", "structure_id",
    "calculation_id", "run_id",  # run_id should be run_ulid
}

# Forbidden dataclass/DTO field names
FORBIDDEN_FIELD_NAMES = {
    "id",  # Should be ulid
    "project_id", "calc_id", "step_id", "structure_id",
    "calculation_id", "run_id",
}

# Forbidden step_type patterns in class fields (must be step_type_spec or step_type_gen)
FORBIDDEN_STEP_TYPE_PATTERNS = {
    "step_type",  # Ambiguous - must be step_type_spec or step_type_gen
}

# Classes that legitimately use 'id' for non-ULID purposes
# These are NOT QMatSuite resource identities
ALLOWLISTED_ID_CLASSES = {
    # JSON-RPC protocol uses id for request/response correlation
    "RPCRequest",
    "RPCResponse",
    # Job identifiers in execution graph (e.g., "step_00", "s_t")
    "Job",
    # Journal entries have their own ID system
    "JournalEntry",
    # Library metadata has its own ID (not ULID)
    "LibraryMetadata",
    # Workflow templates have their own ID scheme
    "WorkflowTemplate",
    # History events have their own ID
    "HistoryEvent",
    # Run revisions have their own ID
    "RunRevision",
}

# NOTE: External API dict keys (e.g., OPTIMADE API's "id" field) are NOT scanned by this gate.
# This gate only checks:
# 1. Meta blocks in our persisted YAML/JSON resources (__qv_meta__, meta:)
# 2. Python class/dataclass field definitions (class Foo: id: str)
#
# External API dict access like `.get("id")` on OPTIMADE responses is exempt because:
# - OPTIMADE is an external standard (https://optimade.org) with its own `id` field
# - These are runtime dict accesses, not class field definitions
# - Our resource files don't store raw OPTIMADE responses in meta blocks

# ============================================================================
# Allowlist matching
# ============================================================================

def is_allowlisted(path: Path) -> bool:
    """Check if a file matches any allowlist pattern."""
    import fnmatch
    rel_path = str(path.relative_to(REPO_ROOT))
    for pattern in ALLOWLIST_PATTERNS:
        if fnmatch.fnmatch(rel_path, pattern):
            return True
    return False

# ============================================================================
# YAML/JSON scanning
# ============================================================================

class ResourceViolation:
    """Represents a violation in a YAML/JSON resource file."""
    def __init__(self, file: Path, line: int, key: str, context: str, violation_type: str):
        self.file = file
        self.line = line
        self.key = key
        self.context = context
        self.violation_type = violation_type

    def __str__(self):
        return f"{self.file}:{self.line} - {self.violation_type}: key '{self.key}' in {self.context}"


def scan_yaml_file(file_path: Path) -> List[ResourceViolation]:
    """Scan a YAML file for forbidden identity keys."""
    violations = []

    try:
        content = file_path.read_text()
        lines = content.split('\n')
    except Exception:
        return violations

    # Scan for forbidden keys in meta blocks
    in_meta_block = False
    meta_indent = 0

    for line_num, line in enumerate(lines, 1):
        stripped = line.strip()

        # Detect meta block start
        if stripped.startswith("meta:") or stripped.startswith("__qv_meta__:"):
            in_meta_block = True
            meta_indent = len(line) - len(line.lstrip())
            continue

        # Check if we're still in meta block (based on indentation)
        if in_meta_block:
            current_indent = len(line) - len(line.lstrip()) if stripped else meta_indent + 1
            if current_indent <= meta_indent and stripped:
                in_meta_block = False

        # Check for forbidden keys in meta blocks
        if in_meta_block:
            for forbidden in FORBIDDEN_META_KEYS:
                # Match "id:" or "id :" at the start of the line (in YAML)
                if re.match(rf'^\s*{forbidden}\s*:', stripped):
                    violations.append(ResourceViolation(
                        file=file_path,
                        line=line_num,
                        key=forbidden,
                        context="meta block",
                        violation_type="FORBIDDEN_META_KEY"
                    ))

        # Check for forbidden resource ID keys anywhere
        for forbidden in FORBIDDEN_RESOURCE_ID_KEYS:
            if re.match(rf'^\s*{forbidden}\s*:', stripped):
                violations.append(ResourceViolation(
                    file=file_path,
                    line=line_num,
                    key=forbidden,
                    context="resource",
                    violation_type="FORBIDDEN_RESOURCE_ID"
                ))

        # Check for ambiguous step_type (not in a comment)
        if not stripped.startswith("#"):
            if re.match(r'^\s*step_type\s*:', stripped):
                # This is ambiguous - should be step_type_spec or step_type_gen
                violations.append(ResourceViolation(
                    file=file_path,
                    line=line_num,
                    key="step_type",
                    context="step definition",
                    violation_type="AMBIGUOUS_STEP_TYPE"
                ))

    return violations


def scan_json_file(file_path: Path) -> List[ResourceViolation]:
    """Scan a JSON file for forbidden identity keys."""
    violations = []

    try:
        content = file_path.read_text()
        data = json.loads(content)
    except Exception:
        return violations

    def scan_dict(d: dict, path: str = "", line_hint: int = 1):
        """Recursively scan a dict for forbidden keys."""
        for key, value in d.items():
            current_path = f"{path}.{key}" if path else key

            # Check meta blocks
            if key in ("meta", "__qv_meta__"):
                if isinstance(value, dict):
                    for forbidden in FORBIDDEN_META_KEYS:
                        if forbidden in value:
                            violations.append(ResourceViolation(
                                file=file_path,
                                line=line_hint,
                                key=forbidden,
                                context=f"meta block at {current_path}",
                                violation_type="FORBIDDEN_META_KEY"
                            ))

            # Check for forbidden resource ID keys
            if key in FORBIDDEN_RESOURCE_ID_KEYS:
                violations.append(ResourceViolation(
                    file=file_path,
                    line=line_hint,
                    key=key,
                    context=current_path,
                    violation_type="FORBIDDEN_RESOURCE_ID"
                ))

            # Check for ambiguous step_type
            if key == "step_type":
                violations.append(ResourceViolation(
                    file=file_path,
                    line=line_hint,
                    key=key,
                    context=current_path,
                    violation_type="AMBIGUOUS_STEP_TYPE"
                ))

            # Recurse into nested dicts
            if isinstance(value, dict):
                scan_dict(value, current_path, line_hint)
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        scan_dict(item, f"{current_path}[{i}]", line_hint)

    if isinstance(data, dict):
        scan_dict(data)
    elif isinstance(data, list):
        for i, item in enumerate(data):
            if isinstance(item, dict):
                scan_dict(item, f"[{i}]")

    return violations


def scan_resource_files() -> List[ResourceViolation]:
    """Scan all YAML/JSON resource files for violations."""
    all_violations = []
    allowlisted = []

    for dir_path in RESOURCE_DIRS:
        if not dir_path.exists():
            continue

        for ext in ["*.yaml", "*.yml", "*.json"]:
            for file_path in dir_path.rglob(ext):
                if is_allowlisted(file_path):
                    allowlisted.append(file_path)
                    continue

                if ext.endswith("json"):
                    violations = scan_json_file(file_path)
                else:
                    violations = scan_yaml_file(file_path)

                all_violations.extend(violations)

    # Print allowlisted files
    for path in allowlisted:
        print(f"ALLOWLISTED: {path}")

    return all_violations


# ============================================================================
# Python source scanning
# ============================================================================

class PythonViolation:
    """Represents a violation in Python source code."""
    def __init__(self, file: Path, line: int, field_name: str, class_name: str, violation_type: str):
        self.file = file
        self.line = line
        self.field_name = field_name
        self.class_name = class_name
        self.violation_type = violation_type

    def __str__(self):
        return f"{self.file}:{self.line} - {self.violation_type}: field '{self.field_name}' in class '{self.class_name}'"


class DataclassFieldVisitor(ast.NodeVisitor):
    """AST visitor to find forbidden field names in dataclasses and classes."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.violations: List[PythonViolation] = []
        self.current_class: str = ""

    def visit_ClassDef(self, node: ast.ClassDef):
        """Visit class definitions to check for forbidden fields."""
        old_class = self.current_class
        self.current_class = node.name

        # Check if this is a dataclass
        is_dataclass = any(
            (isinstance(d, ast.Name) and d.id == "dataclass") or
            (isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id == "dataclass")
            for d in node.decorator_list
        )

        # Scan class body for assignments (field definitions)
        for item in node.body:
            # Check annotated assignments (field: type = value)
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                field_name = item.target.id
                self._check_field(field_name, node.name, item.lineno)

            # Check simple assignments
            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        self._check_field(target.id, node.name, item.lineno)

        # Continue visiting nested classes
        self.generic_visit(node)
        self.current_class = old_class

    def _check_field(self, field_name: str, class_name: str, line: int):
        """Check if a field name is forbidden."""
        # Check forbidden identity field names
        if field_name in FORBIDDEN_FIELD_NAMES:
            # Skip allowlisted classes that use 'id' for non-ULID purposes
            if field_name == "id" and class_name in ALLOWLISTED_ID_CLASSES:
                return  # Allowlisted: this class uses 'id' for non-ULID purposes

            self.violations.append(PythonViolation(
                file=self.file_path,
                line=line,
                field_name=field_name,
                class_name=class_name,
                violation_type="FORBIDDEN_FIELD_NAME"
            ))

        # Check ambiguous step_type
        if field_name in FORBIDDEN_STEP_TYPE_PATTERNS:
            self.violations.append(PythonViolation(
                file=self.file_path,
                line=line,
                field_name=field_name,
                class_name=class_name,
                violation_type="AMBIGUOUS_STEP_TYPE_FIELD"
            ))


def scan_python_file(file_path: Path) -> List[PythonViolation]:
    """Scan a Python file for forbidden field names."""
    try:
        content = file_path.read_text()
        tree = ast.parse(content)
    except Exception:
        return []

    visitor = DataclassFieldVisitor(file_path)
    visitor.visit(tree)
    return visitor.violations


def scan_python_files() -> List[PythonViolation]:
    """Scan all Python source files for violations."""
    all_violations = []
    allowlisted = []

    for dir_path in PYTHON_DIRS:
        if not dir_path.exists():
            continue

        for file_path in dir_path.rglob("*.py"):
            if is_allowlisted(file_path):
                allowlisted.append(file_path)
                continue

            violations = scan_python_file(file_path)
            all_violations.extend(violations)

    # Print allowlisted files
    for path in allowlisted:
        print(f"ALLOWLISTED: {path}")

    return all_violations


# ============================================================================
# Tests
# ============================================================================

class TestNoLegacyIdentityFields:
    """Gate tests to enforce no legacy identity fields."""

    def test_no_forbidden_keys_in_yaml_json_resources(self):
        """
        Gate: No forbidden identity keys in YAML/JSON resource files.

        Scans tests/fixtures/, tests/data/, src/quantumvitas/resources/ for:
        - 'id' in meta blocks (should be 'ulid')
        - project_id, calc_id, step_id, structure_id (should be *_ulid)
        - ambiguous step_type (should be step_type_spec or step_type_gen)
        """
        violations = scan_resource_files()

        if violations:
            report = "\n\n=== LEGACY IDENTITY FIELD VIOLATIONS ===\n"
            report += f"Found {len(violations)} violation(s):\n\n"
            for v in violations:
                report += f"  {v}\n"
            report += "\n=== END VIOLATIONS ===\n"
            pytest.fail(report)

    def test_no_forbidden_field_names_in_python_source(self):
        """
        Gate: No forbidden field names in Python dataclasses/DTOs.

        Scans src/ for class fields named:
        - id (should be ulid)
        - project_id, calc_id, step_id, structure_id (should be *_ulid)
        - step_type (should be step_type_spec or step_type_gen)
        """
        violations = scan_python_files()

        if violations:
            report = "\n\n=== PYTHON FIELD NAME VIOLATIONS ===\n"
            report += f"Found {len(violations)} violation(s):\n\n"
            for v in violations:
                report += f"  {v}\n"
            report += "\n=== END VIOLATIONS ===\n"
            pytest.fail(report)


# ============================================================================
# CLI for manual scanning
# ============================================================================

if __name__ == "__main__":
    print("=== Scanning YAML/JSON Resources ===")
    resource_violations = scan_resource_files()
    print(f"\nFound {len(resource_violations)} resource violation(s)")
    for v in resource_violations:
        print(f"  {v}")

    print("\n=== Scanning Python Source ===")
    python_violations = scan_python_files()
    print(f"\nFound {len(python_violations)} Python violation(s)")
    for v in python_violations:
        print(f"  {v}")

    total = len(resource_violations) + len(python_violations)
    print(f"\n=== TOTAL: {total} violation(s) ===")
    exit(1 if total > 0 else 0)
