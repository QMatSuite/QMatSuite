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


def get_canonical_qvservice_methods() -> set[str]:
    """Get all method names from canonical QVService."""
    service_file = Path("src/quantumvitas/api/service.py")
    if not service_file.exists():
        return set()

    methods = set()
    try:
        content = service_file.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(service_file))
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "QVService":
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        methods.add(item.name)
                    elif isinstance(item, ast.AsyncFunctionDef):
                        methods.add(item.name)
    except Exception:
        pass

    return methods


class QVServiceCallVisitor(ast.NodeVisitor):
    """AST visitor to collect QVService method calls."""
    
    def __init__(self, canonical_methods: set[str], file_path: Path):
        self.canonical_methods = canonical_methods
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
                # Static call: QVService.method()
                if node.func.value.id == self.qvservice_alias:
                    method_name = node.func.attr
                    if method_name not in self.canonical_methods:
                        self.dangling_calls.append({
                            "file": str(self.file_path),
                            "line": node.lineno,
                            "method": f"{self.qvservice_alias}.{method_name}()",
                            "method_name": method_name,
                        })
            elif isinstance(node.func.value, ast.Attribute):
                # Nested: something.QVService.method() - check if it's QVService
                if (isinstance(node.func.value.value, ast.Name) and 
                    node.func.value.value.id == self.qvservice_alias):
                    method_name = node.func.attr
                    if method_name not in self.canonical_methods:
                        self.dangling_calls.append({
                            "file": str(self.file_path),
                            "line": node.lineno,
                            "method": f"{self.qvservice_alias}.{method_name}()",
                            "method_name": method_name,
                        })
        self.generic_visit(node)


def scan_file(file_path: Path, canonical_methods: set[str]) -> list[dict[str, Any]]:
    """Scan a single file for dangling QVService calls."""
    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(file_path))
        
        visitor = QVServiceCallVisitor(canonical_methods, file_path)
        visitor.visit(tree)
        
        return visitor.dangling_calls
    except (SyntaxError, UnicodeDecodeError, Exception):
        return []


def scan_directory(directory: Path, canonical_methods: set[str]) -> list[dict[str, Any]]:
    """Scan a directory for dangling QVService calls."""
    all_dangling = []
    
    for py_file in directory.rglob("*.py"):
        # Skip vault and test files for now (focus on production code)
        if "_vault" in str(py_file) or "test_" in py_file.name:
            continue
        
        dangling = scan_file(py_file, canonical_methods)
        all_dangling.extend(dangling)
    
    return all_dangling


def main():
    """Main entry point."""
    canonical_methods = get_canonical_qvservice_methods()
    
    if not canonical_methods:
        print("ERROR: Could not load canonical QVService methods", file=sys.stderr)
        sys.exit(1)
    
    # Scan src/quantumvitas for production code
    src_dir = Path("src/quantumvitas")
    dangling_calls = scan_directory(src_dir, canonical_methods)
    
    if "--json" in sys.argv:
        output = {
            "canonical_methods_count": len(canonical_methods),
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
