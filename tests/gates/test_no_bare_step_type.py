"""
Gate D: No bare step_type in code surface.

Fail if in src/ or tests/:
- any function/method parameter named exactly step_type
- any dataclass/DTO/TypedDict field named exactly step_type
- any dict literal key exactly "step_type" in non-docstring contexts
- any keyword argument step_type=... in function calls

Allow only:
- docstrings/comments
- local variables (Name nodes)
"""

import ast
import sys
from pathlib import Path
from typing import List, Dict, Set
from collections import defaultdict


def is_string_node(node):
    """Check if node is a string constant (Python 3.8+)."""
    if isinstance(node, ast.Constant):
        return isinstance(node.value, str)
    return False


class BareStepTypeChecker(ast.NodeVisitor):
    """AST visitor to find forbidden bare step_type occurrences."""
    
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.violations: List[Dict] = []
        self.current_function = None
        self.local_vars: Set[str] = set()
        
    def visit_FunctionDef(self, node):
        """Check function parameters."""
        old_function = self.current_function
        old_locals = self.local_vars.copy()
        self.current_function = node.name
        self.local_vars = set()
        
        # Check parameters
        for arg in node.args.args:
            if arg.arg == "step_type":
                self.violations.append({
                    "type": "FORBIDDEN_PARAM",
                    "file": str(self.file_path),
                    "line": node.lineno,
                    "col": node.col_offset,
                    "context": f"function {node.name}",
                })
        
        self.generic_visit(node)
        
        self.current_function = old_function
        self.local_vars = old_locals
    
    def visit_AsyncFunctionDef(self, node):
        """Check async function parameters."""
        self.visit_FunctionDef(node)
    
    def visit_ClassDef(self, node):
        """Check class-level fields (dataclass fields, TypedDict keys)."""
        # Check for dataclass decorator
        is_dataclass = any(
            isinstance(d, ast.Name) and d.id == "dataclass"
            or isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id == "dataclass"
            for d in node.decorator_list
        )
        
        # Check for TypedDict
        is_typeddict = any(
            isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id == "TypedDict"
            for d in node.decorator_list
        )
        
        # Visit class body
        for item in node.body:
            if isinstance(item, ast.AnnAssign):
                # Check for field assignments (dataclass fields)
                if isinstance(item.target, ast.Name) and item.target.id == "step_type":
                    if is_dataclass:
                        self.violations.append({
                            "type": "FORBIDDEN_FIELD",
                            "file": str(self.file_path),
                            "line": item.lineno,
                            "col": item.col_offset,
                            "context": f"class {node.name} (dataclass)",
                        })
            elif isinstance(item, ast.Assign):
                # Check for TypedDict key assignments
                for target in item.targets:
                    if isinstance(target, ast.Name) and target.id == "step_type":
                        if is_typeddict:
                            self.violations.append({
                                "type": "FORBIDDEN_FIELD",
                                "file": str(self.file_path),
                                "line": item.lineno,
                                "col": item.col_offset,
                                "context": f"class {node.name} (TypedDict)",
                            })
        
        self.generic_visit(node)
    
    def visit_Assign(self, node):
        """Track local variable assignments (allowed)."""
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "step_type":
                self.local_vars.add("step_type")
        self.generic_visit(node)
    
    def visit_Subscript(self, node):
        """Check dict["step_type"]."""
        if isinstance(node.value, ast.Name):
            # Check for dict["step_type"]
            if isinstance(node.slice, ast.Constant) and node.slice.value == "step_type":
                self.violations.append({
                    "type": "FORBIDDEN_DICT_KEY",
                    "file": str(self.file_path),
                    "line": node.lineno,
                    "col": node.col_offset,
                    "context": f"in {self.current_function or '<module>'}",
                })
            elif is_string_node(node.slice) and isinstance(node.slice, ast.Constant) and node.slice.value == "step_type":
                self.violations.append({
                    "type": "FORBIDDEN_DICT_KEY",
                    "file": str(self.file_path),
                    "line": node.lineno,
                    "col": node.col_offset,
                    "context": f"in {self.current_function or '<module>'}",
                })
        self.generic_visit(node)
    
    def visit_Call(self, node):
        """Check for .get("step_type") and step_type= keyword arguments."""
        # Check for .get("step_type")
        if isinstance(node.func, ast.Attribute) and node.func.attr == "get":
            if node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == "step_type":
                self.violations.append({
                    "type": "FORBIDDEN_DICT_KEY",
                    "file": str(self.file_path),
                    "line": node.lineno,
                    "col": node.col_offset,
                    "context": f"in {self.current_function or '<module>'}",
                })
            elif node.args and is_string_node(node.args[0]) and isinstance(node.args[0], ast.Constant) and node.args[0].value == "step_type":
                self.violations.append({
                    "type": "FORBIDDEN_DICT_KEY",
                    "file": str(self.file_path),
                    "line": node.lineno,
                    "col": node.col_offset,
                    "context": f"in {self.current_function or '<module>'}",
                })
        
        # Check for step_type= keyword arguments
        for keyword in node.keywords:
            if keyword.arg == "step_type":
                self.violations.append({
                    "type": "FORBIDDEN_KWARG",
                    "file": str(self.file_path),
                    "line": node.lineno,
                    "col": node.col_offset,
                    "context": f"in {self.current_function or '<module>'}",
                })
        
        self.generic_visit(node)
    
    def visit_Dict(self, node):
        """Check dict literal keys like {"step_type": ...}."""
        for key, value in zip(node.keys, node.values):
            if isinstance(key, ast.Constant) and key.value == "step_type":
                self.violations.append({
                    "type": "FORBIDDEN_DICT_KEY",
                    "file": str(self.file_path),
                    "line": key.lineno,
                    "col": key.col_offset,
                    "context": f"in {self.current_function or '<module>'}",
                })
            elif is_string_node(key) and isinstance(key, ast.Constant) and key.value == "step_type":
                self.violations.append({
                    "type": "FORBIDDEN_DICT_KEY",
                    "file": str(self.file_path),
                    "line": key.lineno,
                    "col": key.col_offset,
                    "context": f"in {self.current_function or '<module>'}",
                })
        self.generic_visit(node)


def check_file(file_path: Path) -> List[Dict]:
    """Check a single Python file."""
    try:
        content = file_path.read_text()
        tree = ast.parse(content, filename=str(file_path))
        checker = BareStepTypeChecker(file_path)
        checker.visit(tree)
        return checker.violations
    except SyntaxError:
        return []
    except Exception:
        return []


def test_no_bare_step_type_in_code():
    """Gate D: Fail if any forbidden bare step_type occurrences found."""
    repo_root = Path(__file__).parent.parent.parent
    src_dir = repo_root / "src"
    tests_dir = repo_root / "tests"
    
    all_violations = []
    
    # Check src/
    if src_dir.exists():
        for py_file in src_dir.rglob("*.py"):
            violations = check_file(py_file)
            all_violations.extend(violations)
    
    # Check tests/
    if tests_dir.exists():
        for py_file in tests_dir.rglob("*.py"):
            violations = check_file(py_file)
            all_violations.extend(violations)
    
    # Group violations by type
    violations_by_type = defaultdict(list)
    for v in all_violations:
        violations_by_type[v["type"]].append(v)
    
    # Build error message
    if all_violations:
        error_lines = [
            f"Found {len(all_violations)} forbidden bare 'step_type' occurrences:",
            ""
        ]
        
        for vtype in ["FORBIDDEN_PARAM", "FORBIDDEN_FIELD", "FORBIDDEN_DICT_KEY", "FORBIDDEN_KWARG"]:
            if violations_by_type[vtype]:
                error_lines.append(f"{vtype}: {len(violations_by_type[vtype])} occurrences")
                for v in violations_by_type[vtype][:10]:  # Show first 10
                    error_lines.append(f"  {v['file']}:{v['line']}:{v['col']} - {v['context']}")
                if len(violations_by_type[vtype]) > 10:
                    error_lines.append(f"  ... and {len(violations_by_type[vtype]) - 10} more")
                error_lines.append("")
        
        error_msg = "\n".join(error_lines)
        assert False, error_msg
    
    # If we get here, all checks passed
    assert True
