"""
Gate B6: Single SSOT for Mappings (§10.3)

Constitution §10.3: All mapping lookups must call DriverRegistry or GenStepRegistry.
No duplicate mapping dicts in tests/tools.

This gate scans tests and tools for copied mapping dicts that duplicate SSOT.
"""

import ast
import re
from pathlib import Path
from typing import List, Tuple, Set, Optional

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
COMMON_GEN_STEPS = {"scf", "nscf", "relax", "md", "dos", "bands", "bandspw", "wannierprep", "pw2wannier", "wannier", "postwannier", "ph"}

# Payload keys that indicate this is NOT a mapping dict
PAYLOAD_KEYS = {
    "step_type_gen", "step_type_spec", "step_ulid", "calc_ulid", "run_ulid",
    "meta", "status", "steps", "error", "message", "parameters", "cards",
    "structure_ulid", "calculation_ulid", "ulid", "id", "name", "slug",
    "path", "kind", "input", "output", "working_dir", "file", "step_file",
}


def is_skipped(path: Path) -> bool:
    """Check if file should be skipped."""
    import fnmatch
    rel_path = str(path.relative_to(REPO_ROOT))
    for pattern in SKIP_PATTERNS:
        if fnmatch.fnmatch(rel_path, pattern):
            return True
    return False


def is_gen_step_type(s: str) -> bool:
    """Check if string looks like a GEN step type (no underscore, lowercase)."""
    if not s or "_" in s:
        return False
    return s.lower() in COMMON_GEN_STEPS or (s.islower() and s.isalpha() and len(s) >= 2)


def is_spec_step_type(s: str) -> bool:
    """Check if string looks like a SPEC step type (prefix_gen format)."""
    if not s or "_" not in s:
        return False
    parts = s.split("_", 1)
    if len(parts) != 2:
        return False
    prefix, gen = parts
    return prefix.lower() in ENGINE_PREFIXES and is_gen_step_type(gen)


def extract_dict_keys_and_values(node: ast.Dict) -> Tuple[List[str], List[str]]:
    """Extract string keys and values from an AST Dict node."""
    keys = []
    values = []
    for key_node, value_node in zip(node.keys, node.values):
        # Handle Python 3.8+ (ast.Constant) and older (ast.Str)
        if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
            keys.append(key_node.value)
        elif hasattr(ast, 'Str') and isinstance(key_node, ast.Str):
            keys.append(key_node.s)
        
        if isinstance(value_node, ast.Constant) and isinstance(value_node.value, str):
            values.append(value_node.value)
        elif hasattr(ast, 'Str') and isinstance(value_node, ast.Str):
            values.append(value_node.s)
    
    return keys, values


def has_payload_keys(keys: List[str]) -> bool:
    """Check if dict contains any payload keys (indicates it's not a mapping)."""
    key_set = {k.lower() for k in keys}
    return bool(key_set & PAYLOAD_KEYS)


def is_mapping_dict(node: ast.Dict, context_line: Optional[str] = None, parent_node: Optional[ast.AST] = None) -> bool:
    """
    Check if a dict looks like a step type mapping dict.
    
    Returns True only if:
    - Dict has ≥2 entries
    - ≥80% of keys pass is_gen_step_type(key)
    - ≥80% of values pass is_spec_step_type(value)
    - Dict does NOT contain payload keys
    - Dict is NOT in a test assertion (assert statement)
    - (Optional) Context suggests mapping (variable name contains map/mapping/etc)
    """
    if len(node.keys) < 2:
        return False
    
    # Skip if this is in an assert statement (test assertion, not production mapping)
    if parent_node and isinstance(parent_node, ast.Assert):
        return False
    
    keys, values = extract_dict_keys_and_values(node)
    
    # Skip if contains payload keys (definitely not a mapping)
    if has_payload_keys(keys):
        return False
    
    # Check if keys look like GEN steps
    gen_key_count = sum(1 for k in keys if is_gen_step_type(k))
    gen_key_ratio = gen_key_count / len(keys) if keys else 0
    
    # Check if values look like SPEC steps
    spec_value_count = sum(1 for v in values if is_spec_step_type(v))
    spec_value_ratio = spec_value_count / len(values) if values else 0
    
    # Require ≥80% match for both keys and values
    if gen_key_ratio < 0.8 or spec_value_ratio < 0.8:
        return False
    
    # Optional: check context for mapping-related keywords
    if context_line:
        context_lower = context_line.lower()
        mapping_keywords = ["map", "mapping", "materialization", "dispatch", "registry"]
        if any(kw in context_lower for kw in mapping_keywords):
            return True  # Strong signal
    
    # If we get here, it looks like a mapping dict
    return True


class MappingDictVisitor(ast.NodeVisitor):
    """AST visitor to find mapping dicts."""
    
    def __init__(self, file_path: Path, lines: List[str]):
        self.file_path = file_path
        self.lines = lines
        self.violations: List[Tuple[int, str]] = []
        self.parent_stack: List[ast.AST] = []
    
    def visit(self, node: ast.AST):
        """Visit node and track parent stack."""
        self.parent_stack.append(node)
        try:
            super().visit(node)
        finally:
            self.parent_stack.pop()
    
    def visit_Dict(self, node: ast.Dict):
        """Visit dict nodes and check if they look like mappings."""
        # Check if this dict is in an assert statement by walking up parent stack
        in_assert = False
        for parent in self.parent_stack:
            if isinstance(parent, ast.Assert):
                in_assert = True
                break
            # Also check Compare nodes (assert x == {...})
            if isinstance(parent, ast.Compare):
                # Check if parent of Compare is Assert
                parent_idx = self.parent_stack.index(parent) if parent in self.parent_stack else -1
                if parent_idx > 0:
                    grandparent = self.parent_stack[parent_idx - 1]
                    if isinstance(grandparent, ast.Assert):
                        in_assert = True
                        break
        
        # Get context line (the line where this dict appears)
        context_line = None
        if node.lineno <= len(self.lines):
            context_line = self.lines[node.lineno - 1]
            # Look backwards for assignment or variable context
            for i in range(max(0, node.lineno - 3), node.lineno):
                if i < len(self.lines):
                    line = self.lines[i]
                    if "=" in line or ":" in line:
                        context_line = line
                        break
        
        # Skip if in assert (test assertion, not production mapping)
        if in_assert:
            self.generic_visit(node)
            return
        
        if is_mapping_dict(node, context_line, None):
            self.violations.append((
                node.lineno,
                f"Hardcoded mapping dict found (line {node.lineno}). Use DriverRegistry or GenStepRegistry instead."
            ))
        
        self.generic_visit(node)


def scan_for_mapping_dicts(content: str, file_path: Path) -> List[Tuple[int, str]]:
    """Scan for hardcoded mapping dicts using AST parsing."""
    try:
        tree = ast.parse(content, filename=str(file_path))
        lines = content.split('\n')
        visitor = MappingDictVisitor(file_path, lines)
        visitor.visit(tree)
        return visitor.violations
    except (SyntaxError, UnicodeDecodeError):
        # Skip files with syntax errors
        return []


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
