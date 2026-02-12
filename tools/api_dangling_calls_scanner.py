"""
Dangling API Call Scanner

AST-based scanner to detect calls to QVService methods that don't exist
on the canonical quantumvitas.api.service.QVService class.
"""

import ast
import json
import sys
from pathlib import Path
from typing import Any


def get_canonical_qvservice_methods() -> tuple[set[str], dict[str, set[str]]]:
    """Get all method names and nested class methods from canonical QVService.
    
    Returns:
        (direct_methods, nested_class_methods) where:
        - direct_methods: set of method names directly on QVService
        - nested_class_methods: dict mapping nested class name to set of its method names
    """
    service_file = Path("src/quantumvitas/api/service.py")
    if not service_file.exists():
        return set(), {}

    direct_methods = set()
    nested_class_methods = {}
    try:
        content = service_file.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(service_file))

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "QVService":
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        direct_methods.add(item.name)
                    elif isinstance(item, ast.AsyncFunctionDef):
                        direct_methods.add(item.name)
                    elif isinstance(item, ast.ClassDef):
                        # Nested class: collect its methods
                        nested_methods = set()
                        for nested_item in item.body:
                            if isinstance(nested_item, ast.FunctionDef):
                                nested_methods.add(nested_item.name)
                            elif isinstance(nested_item, ast.AsyncFunctionDef):
                                nested_methods.add(nested_item.name)
                        nested_class_methods[item.name] = nested_methods
    except Exception:
        pass

    return direct_methods, nested_class_methods


class QVServiceCallVisitor(ast.NodeVisitor):
    """AST visitor to collect QVService method calls."""
    
    def __init__(self, direct_methods: set[str], nested_class_methods: dict[str, set[str]], file_path: Path):
        self.direct_methods = direct_methods
        self.nested_class_methods = nested_class_methods
        self.file_path = file_path
        self.dangling_calls = []
        self.imports_qvservice = False
        self.qvservice_alias = "QVService"
    
    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Track imports of QVService from quantumvitas.api."""
        if node.module == "quantumvitas.api":
            for alias in node.names:
                if alias.name == "QVService":
                    self.imports_qvservice = True
                    self.qvservice_alias = alias.asname or "QVService"
        self.generic_visit(node)
    
    def visit_Call(self, node: ast.Call):
        """Collect QVService.method() calls."""
        if isinstance(node.func, ast.Attribute):
            # Check if it's QVService.method() or instance.method()
            if isinstance(node.func.value, ast.Name):
                # Static call: QVService.method() or QVService.NestedClass()
                if node.func.value.id == self.qvservice_alias:
                    method_name = node.func.attr
                    # Allow nested class instantiation (QVService.Analysis(self) is valid)
                    if method_name in self.nested_class_methods:
                        # This is a nested class instantiation, which is valid
                        pass
                    elif method_name not in self.direct_methods:
                        self.dangling_calls.append({
                            "file": str(self.file_path),
                            "line": node.lineno,
                            "method": f"{self.qvservice_alias}.{method_name}()",
                            "method_name": method_name,
                        })
            elif isinstance(node.func.value, ast.Attribute):
                # Nested: QVService.NestedClass.method() or something.QVService.method()
                if isinstance(node.func.value.value, ast.Name):
                    if node.func.value.value.id == self.qvservice_alias:
                        # QVService.NestedClass.method()
                        nested_class_name = node.func.value.attr
                        method_name = node.func.attr
                        # Check if nested_class is a valid nested class and method is valid
                        if nested_class_name in self.nested_class_methods:
                            if method_name not in self.nested_class_methods[nested_class_name]:
                                self.dangling_calls.append({
                                    "file": str(self.file_path),
                                    "line": node.lineno,
                                    "method": f"{self.qvservice_alias}.{nested_class_name}.{method_name}()",
                                    "method_name": method_name,
                                })
                        else:
                            # Nested class doesn't exist
                            self.dangling_calls.append({
                                "file": str(self.file_path),
                                "line": node.lineno,
                                "method": f"{self.qvservice_alias}.{nested_class_name}.{method_name}()",
                                "method_name": method_name,
                            })
        self.generic_visit(node)


def scan_file(file_path: Path, direct_methods: set[str], nested_class_methods: dict[str, set[str]]) -> list[dict[str, Any]]:
    """Scan a single file for dangling QVService calls."""
    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(file_path))
        
        visitor = QVServiceCallVisitor(direct_methods, nested_class_methods, file_path)
        visitor.visit(tree)
        
        return visitor.dangling_calls
    except (SyntaxError, UnicodeDecodeError, Exception):
        return []


def scan_directory(directory: Path, direct_methods: set[str], nested_class_methods: dict[str, set[str]]) -> list[dict[str, Any]]:
    """Scan a directory for dangling QVService calls."""
    all_dangling = []
    
    for py_file in directory.rglob("*.py"):
        # Skip vault and test files for now (focus on production code)
        if "_vault" in str(py_file) or "test_" in py_file.name:
            continue
        
        dangling = scan_file(py_file, direct_methods, nested_class_methods)
        all_dangling.extend(dangling)
    
    return all_dangling


def main():
    """Main entry point."""
    direct_methods, nested_class_methods = get_canonical_qvservice_methods()
    
    if not direct_methods and not nested_class_methods:
        print("ERROR: Could not load canonical QVService methods", file=sys.stderr)
        sys.exit(1)
    
    # Scan src/quantumvitas for production code
    src_dir = Path("src/quantumvitas")
    dangling_calls = scan_directory(src_dir, direct_methods, nested_class_methods)
    
    if "--json" in sys.argv:
        total_methods = len(direct_methods) + sum(len(methods) for methods in nested_class_methods.values())
        output = {
            "canonical_methods_count": total_methods,
            "dangling_calls_count": len(dangling_calls),
            "dangling_calls": dangling_calls,
        }
        print(json.dumps(output, indent=2))
    else:
        if dangling_calls:
            print("ERROR: Dangling API calls detected:")
            for call in dangling_calls:
                print(f"  - {call['file']}:{call['line']}: {call['method']}")
                print(f"    Method '{call['method_name']}' not found on quantumvitas.api.service.QVService")
                print(f"    Suggestion: Method may exist on quantumvitas._vault._legacy_service.QVService - needs migration")
            sys.exit(1)
        else:
            print("PASS: No dangling calls found")


if __name__ == "__main__":
    main()
