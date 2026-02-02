#!/usr/bin/env python3
"""
Analyze bare step_type occurrences and categorize them.

Categories:
- DOC_ONLY: Comments/docstrings ✅ allowed
- LOCAL_VAR: Local variable assignments ✅ allowed
- FORBIDDEN_PARAM: Function/method parameter named step_type ❌ must fix
- FORBIDDEN_FIELD: Dataclass/DTO field named step_type ❌ must fix
- FORBIDDEN_DICT_KEY: dict["step_type"] or .get("step_type") ❌ must fix
- FORBIDDEN_KWARG: Calls with step_type=... ❌ must fix
"""

import ast
import re
from pathlib import Path
from typing import Dict, List, Tuple, Set
from collections import defaultdict
import sys

# Compatibility: ast.Str was removed in Python 3.8+, use ast.Constant instead
def is_string_node(node):
    """Check if node is a string constant (compatible with Python 3.8+)."""
    if isinstance(node, ast.Constant):
        return isinstance(node.value, str)
    # Python < 3.8 compatibility (though we likely don't need this)
    return False


class StepTypeAnalyzer(ast.NodeVisitor):
    """AST visitor to find and categorize bare step_type occurrences."""
    
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.categories = defaultdict(list)
        self.current_function = None
        self.local_vars: Set[str] = set()
        
    def visit_FunctionDef(self, node):
        """Track function context and parameters."""
        old_function = self.current_function
        old_locals = self.local_vars.copy()
        self.current_function = node.name
        self.local_vars = set()
        
        # Check parameters
        for arg in node.args.args:
            if arg.arg == "step_type":
                self.categories["FORBIDDEN_PARAM"].append({
                    "file": str(self.file_path),
                    "line": node.lineno,
                    "col": node.col_offset,
                    "context": f"function {node.name}",
                    "snippet": f"def {node.name}(..., step_type: ...)"
                })
        
        # Check for dataclass decorator
        is_dataclass = any(
            isinstance(d, ast.Name) and d.id == "dataclass"
            or isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id == "dataclass"
            for d in node.decorator_list
        )
        
        self.generic_visit(node)
        
        self.current_function = old_function
        self.local_vars = old_locals
    
    def visit_AsyncFunctionDef(self, node):
        """Track async function context."""
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
                        self.categories["FORBIDDEN_FIELD"].append({
                            "file": str(self.file_path),
                            "line": item.lineno,
                            "col": item.col_offset,
                            "context": f"class {node.name} (dataclass)",
                            "snippet": f"{node.name}.step_type: ..."
                        })
            elif isinstance(item, ast.Assign):
                # Check for TypedDict key assignments
                for target in item.targets:
                    if isinstance(target, ast.Name) and target.id == "step_type":
                        if is_typeddict:
                            self.categories["FORBIDDEN_FIELD"].append({
                                "file": str(self.file_path),
                                "line": item.lineno,
                                "col": item.col_offset,
                                "context": f"class {node.name} (TypedDict)",
                                "snippet": f"{node.name}.step_type = ..."
                            })
        
        self.generic_visit(node)
    
    def visit_Assign(self, node):
        """Track local variable assignments."""
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "step_type":
                # This is a local variable assignment
                self.local_vars.add("step_type")
                self.categories["LOCAL_VAR"].append({
                    "file": str(self.file_path),
                    "line": node.lineno,
                    "col": node.col_offset,
                    "context": f"in {self.current_function or '<module>'}",
                    "snippet": "step_type = ..."
                })
        self.generic_visit(node)
    
    def visit_Subscript(self, node):
        """Check dict["step_type"] or dict.get("step_type")."""
        if isinstance(node.value, ast.Name):
            # Check for dict["step_type"]
            if isinstance(node.slice, ast.Constant) and node.slice.value == "step_type":
                self.categories["FORBIDDEN_DICT_KEY"].append({
                    "file": str(self.file_path),
                    "line": node.lineno,
                    "col": node.col_offset,
                    "context": f"in {self.current_function or '<module>'}",
                    "snippet": f"{node.value.id}['step_type']"
                })
            elif is_string_node(node.slice) and isinstance(node.slice, ast.Constant) and node.slice.value == "step_type":
                self.categories["FORBIDDEN_DICT_KEY"].append({
                    "file": str(self.file_path),
                    "line": node.lineno,
                    "col": node.col_offset,
                    "context": f"in {self.current_function or '<module>'}",
                    "snippet": f"{node.value.id}['step_type']"
                })
        self.generic_visit(node)
    
    def visit_Call(self, node):
        """Check for .get("step_type") and step_type= keyword arguments."""
        # Check for .get("step_type")
        if isinstance(node.func, ast.Attribute) and node.func.attr == "get":
            if node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == "step_type":
                self.categories["FORBIDDEN_DICT_KEY"].append({
                    "file": str(self.file_path),
                    "line": node.lineno,
                    "col": node.col_offset,
                    "context": f"in {self.current_function or '<module>'}",
                    "snippet": "...get('step_type')"
                })
            elif node.args and is_string_node(node.args[0]) and isinstance(node.args[0], ast.Constant) and node.args[0].value == "step_type":
                self.categories["FORBIDDEN_DICT_KEY"].append({
                    "file": str(self.file_path),
                    "line": node.lineno,
                    "col": node.col_offset,
                    "context": f"in {self.current_function or '<module>'}",
                    "snippet": "...get('step_type')"
                })
        
        # Check for step_type= keyword arguments
        for keyword in node.keywords:
            if keyword.arg == "step_type":
                self.categories["FORBIDDEN_KWARG"].append({
                    "file": str(self.file_path),
                    "line": node.lineno,
                    "col": node.col_offset,
                    "context": f"in {self.current_function or '<module>'}",
                    "snippet": "...step_type=..."
                })
        
        self.generic_visit(node)
    
    def visit_Dict(self, node):
        """Check dict literal keys like {"step_type": ...}."""
        for key, value in zip(node.keys, node.values):
            if isinstance(key, ast.Constant) and key.value == "step_type":
                self.categories["FORBIDDEN_DICT_KEY"].append({
                    "file": str(self.file_path),
                    "line": key.lineno,
                    "col": key.col_offset,
                    "context": f"in {self.current_function or '<module>'}",
                    "snippet": "{'step_type': ...}"
                })
            elif is_string_node(key) and isinstance(key, ast.Constant) and key.value == "step_type":
                self.categories["FORBIDDEN_DICT_KEY"].append({
                    "file": str(self.file_path),
                    "line": key.lineno,
                    "col": key.col_offset,
                    "context": f"in {self.current_function or '<module>'}",
                    "snippet": "{'step_type': ...}"
                })
        self.generic_visit(node)


def analyze_file(file_path: Path) -> Dict[str, List]:
    """Analyze a single Python file."""
    try:
        content = file_path.read_text()
        
        # Extract docstrings and comments first (for DOC_ONLY category)
        # (patterns not used directly, but kept for reference)
        
        # Parse AST
        try:
            tree = ast.parse(content, filename=str(file_path))
        except SyntaxError:
            return defaultdict(list)
        
        analyzer = StepTypeAnalyzer(file_path)
        analyzer.visit(tree)
        
        # Check for docstrings/comments with "step_type"
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            # Check comments
            if '#' in line:
                comment_start = line.index('#')
                comment_part = line[comment_start:]
                if 'step_type' in comment_part and 'step_type_' not in comment_part:
                    analyzer.categories["DOC_ONLY"].append({
                        "file": str(file_path),
                        "line": i,
                        "col": comment_start,
                        "context": "comment",
                        "snippet": comment_part[:60]
                    })
        
        # Check docstrings
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Module)):
                docstring = ast.get_docstring(node)
                if docstring and 'step_type' in docstring and 'step_type_' not in docstring:
                    analyzer.categories["DOC_ONLY"].append({
                        "file": str(file_path),
                        "line": node.lineno if hasattr(node, 'lineno') else 1,
                        "col": 0,
                        "context": f"{type(node).__name__} docstring",
                        "snippet": docstring[:60]
                    })
        
        return dict(analyzer.categories)
    except Exception as e:
        print(f"Error analyzing {file_path}: {e}", file=sys.stderr)
        return defaultdict(list)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Analyze bare step_type occurrences")
    parser.add_argument("--src-dir", default="src", help="Source directory")
    parser.add_argument("--tests-dir", default="tests", help="Tests directory")
    parser.add_argument("--output", help="Output file (default: stdout)")
    args = parser.parse_args()
    
    src_dir = Path(args.src_dir)
    tests_dir = Path(args.tests_dir)
    
    all_categories = defaultdict(list)
    
    # Analyze src/
    if src_dir.exists():
        for py_file in src_dir.rglob("*.py"):
            categories = analyze_file(py_file)
            for cat, items in categories.items():
                all_categories[cat].extend(items)
    
    # Analyze tests/
    if tests_dir.exists():
        for py_file in tests_dir.rglob("*.py"):
            categories = analyze_file(py_file)
            for cat, items in categories.items():
                all_categories[cat].extend(items)
    
    # Generate report
    report_lines = []
    report_lines.append("=" * 80)
    report_lines.append("BARE step_type OCCURRENCE REPORT")
    report_lines.append("=" * 80)
    report_lines.append("")
    
    forbidden_categories = ["FORBIDDEN_PARAM", "FORBIDDEN_FIELD", "FORBIDDEN_DICT_KEY", "FORBIDDEN_KWARG"]
    allowed_categories = ["DOC_ONLY", "LOCAL_VAR"]
    
    total_forbidden = 0
    for cat in forbidden_categories:
        count = len(all_categories[cat])
        total_forbidden += count
        report_lines.append(f"{cat}: {count} occurrences")
        if count > 0:
            report_lines.append("")
            for item in all_categories[cat][:20]:  # Show first 20
                report_lines.append(f"  {item['file']}:{item['line']}:{item['col']} - {item['context']}")
                report_lines.append(f"    {item['snippet']}")
            if count > 20:
                report_lines.append(f"  ... and {count - 20} more")
            report_lines.append("")
    
    report_lines.append("=" * 80)
    report_lines.append(f"TOTAL FORBIDDEN: {total_forbidden}")
    report_lines.append("=" * 80)
    report_lines.append("")
    
    for cat in allowed_categories:
        count = len(all_categories[cat])
        report_lines.append(f"{cat}: {count} occurrences (✅ allowed)")
    
    report = "\n".join(report_lines)
    
    if args.output:
        Path(args.output).write_text(report)
        print(f"Report written to {args.output}")
    else:
        print(report)
    
    # Exit with error code if forbidden occurrences found
    if total_forbidden > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()

