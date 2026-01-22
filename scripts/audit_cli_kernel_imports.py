#!/usr/bin/env python3
"""
Audit CLI kernel imports to generate a dependency manifest.

Scans src/quantumvitas/cli/*.py using AST and reports all forbidden
imports (quantumvitas.core, quantumvitas.calculation, quantumvitas.analysis,
quantumvitas.io, quantumvitas.drivers, quantumvitas.engine, quantumvitas.workflow,
quantumvitas.presets).

Also detects bare resolve_* function calls (not method calls like svc.resolve_*).

Outputs JSON manifest with:
- Total violations
- By module (grouped by imported module)
- By symbol (grouped by imported symbol)
- Bare resolve_* calls
- Line numbers and function context
"""

import ast
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

# Forbidden prefixes (must match test_import_rules.py)
FORBIDDEN_PREFIXES = (
    "quantumvitas.core",
    "quantumvitas.calculation",
    "quantumvitas.analysis",
    "quantumvitas.io",
    "quantumvitas.drivers",
    "quantumvitas.engine",
    "quantumvitas.workflow",
    "quantumvitas.presets",
)

# Bare resolve_* functions that should be called via QVService
BARE_RESOLVE_FUNCTIONS = {
    "resolve_calculation",
    "resolve_step",
    "resolve_structure",
}


class ImportVisitor(ast.NodeVisitor):
    """AST visitor to collect forbidden imports and bare resolve_* calls."""
    
    def __init__(self):
        self.violations: List[Dict[str, Any]] = []
        self.bare_resolve_calls: List[Dict[str, Any]] = []
        self._function_stack: List[str] = []
    
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Track function context."""
        self._function_stack.append(node.name)
        self.generic_visit(node)
        self._function_stack.pop()
    
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Track async function context."""
        self._function_stack.append(node.name)
        self.generic_visit(node)
        self._function_stack.pop()
    
    def visit_Import(self, node: ast.Import) -> None:
        """Check import statements."""
        for alias in node.names:
            module_name = alias.name
            if any(module_name.startswith(prefix) for prefix in FORBIDDEN_PREFIXES):
                self.violations.append({
                    "type": "import",
                    "module": module_name,
                    "symbol": None,
                    "line": node.lineno,
                    "function": self._function_stack[-1] if self._function_stack else None,
                    "asname": alias.asname,
                })
    
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Check import from statements."""
        if node.module is None:
            return
        
        module_name = node.module
        if any(module_name.startswith(prefix) for prefix in FORBIDDEN_PREFIXES):
            if node.names:
                # Import specific symbols
                for alias in node.names:
                    symbol_name = alias.name
                    self.violations.append({
                        "type": "import_from",
                        "module": module_name,
                        "symbol": symbol_name,
                        "line": node.lineno,
                        "function": self._function_stack[-1] if self._function_stack else None,
                        "asname": alias.asname,
                    })
            else:
                # Import * (rare but possible)
                self.violations.append({
                    "type": "import_from",
                    "module": module_name,
                    "symbol": "*",
                    "line": node.lineno,
                    "function": self._function_stack[-1] if self._function_stack else None,
                    "asname": None,
                })
    
    def visit_Call(self, node: ast.Call) -> None:
        """Check for bare resolve_* function calls (not method calls)."""
        # Only check if func is a Name (bare call), not Attribute (method call)
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in BARE_RESOLVE_FUNCTIONS:
                self.bare_resolve_calls.append({
                    "function": func_name,
                    "line": node.lineno,
                    "context": self._function_stack[-1] if self._function_stack else None,
                })
        self.generic_visit(node)


def audit_cli_imports(cli_dir: Path) -> Dict[str, Any]:
    """
    Audit CLI directory for forbidden kernel imports and bare resolve_* calls.
    
    Args:
        cli_dir: Path to CLI directory (src/quantumvitas/cli)
        
    Returns:
        JSON-serializable manifest dict
    """
    all_violations: List[Dict[str, Any]] = []
    all_bare_calls: List[Dict[str, Any]] = []
    by_file: Dict[str, Dict[str, Any]] = {}
    
    # Scan all Python files in CLI directory
    for py_file in sorted(cli_dir.glob("*.py")):
        if py_file.name.startswith("__"):
            continue  # Skip __init__.py, __main__.py
        
        try:
            content = py_file.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(py_file))
        except SyntaxError as e:
            print(f"Warning: Syntax error in {py_file}: {e}", file=sys.stderr)
            continue
        except Exception as e:
            print(f"Warning: Error reading {py_file}: {e}", file=sys.stderr)
            continue
        
        visitor = ImportVisitor()
        visitor.visit(tree)
        
        if visitor.violations or visitor.bare_resolve_calls:
            by_file[str(py_file.relative_to(cli_dir.parent.parent.parent))] = {
                "violations": len(visitor.violations),
                "bare_calls": len(visitor.bare_resolve_calls),
            }
        
        # Add file path to violations
        for violation in visitor.violations:
            violation["file"] = str(py_file.relative_to(cli_dir.parent.parent.parent))
            all_violations.append(violation)
        
        for call in visitor.bare_resolve_calls:
            call["file"] = str(py_file.relative_to(cli_dir.parent.parent.parent))
            all_bare_calls.append(call)
    
    # Build statistics
    by_module: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"count": 0, "lines": [], "functions": set(), "files": set()})
    by_symbol: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"count": 0, "lines": [], "functions": set(), "files": set()})
    
    for violation in all_violations:
        module = violation["module"]
        symbol = violation["symbol"]
        line = violation["line"]
        func = violation["function"]
        file_path = violation.get("file", "unknown")
        
        # By module
        by_module[module]["count"] += 1
        by_module[module]["lines"].append(line)
        by_module[module]["files"].add(file_path)
        if func:
            by_module[module]["functions"].add(func)
        
        # By symbol (if symbol exists)
        if symbol:
            symbol_key = f"{module}:{symbol}"
            by_symbol[symbol_key]["count"] += 1
            by_symbol[symbol_key]["lines"].append(line)
            by_symbol[symbol_key]["files"].add(file_path)
            if func:
                by_symbol[symbol_key]["functions"].add(func)
    
    # Convert sets to lists for JSON serialization
    for module_data in by_module.values():
        module_data["functions"] = sorted(module_data["functions"])
        module_data["lines"] = sorted(set(module_data["lines"]))
        module_data["files"] = sorted(module_data["files"])
    
    for symbol_data in by_symbol.values():
        symbol_data["functions"] = sorted(symbol_data["functions"])
        symbol_data["lines"] = sorted(set(symbol_data["lines"]))
        symbol_data["files"] = sorted(symbol_data["files"])
    
    # Sort by count (descending)
    by_module_sorted = dict(sorted(by_module.items(), key=lambda x: x[1]["count"], reverse=True))
    by_symbol_sorted = dict(sorted(by_symbol.items(), key=lambda x: x[1]["count"], reverse=True))
    
    # Group bare calls by function
    by_bare_function: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"count": 0, "lines": [], "functions": set(), "files": set()})
    for call in all_bare_calls:
        func_name = call["function"]
        by_bare_function[func_name]["count"] += 1
        by_bare_function[func_name]["lines"].append(call["line"])
        by_bare_function[func_name]["files"].add(call["file"])
        if call["context"]:
            by_bare_function[func_name]["functions"].add(call["context"])
    
    for func_data in by_bare_function.values():
        func_data["functions"] = sorted(func_data["functions"])
        func_data["lines"] = sorted(set(func_data["lines"]))
        func_data["files"] = sorted(func_data["files"])
    
    by_bare_function_sorted = dict(sorted(by_bare_function.items(), key=lambda x: x[1]["count"], reverse=True))
    
    return {
        "cli_directory": str(cli_dir),
        "total_violations": len(all_violations),
        "total_bare_resolve_calls": len(all_bare_calls),
        "by_file": by_file,
        "by_module": by_module_sorted,
        "by_symbol": by_symbol_sorted,
        "by_bare_function": by_bare_function_sorted,
    }


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Audit CLI kernel imports")
    parser.add_argument("--json", type=str, help="Output JSON to file")
    args = parser.parse_args()
    
    repo_root = Path(__file__).parent.parent
    cli_dir = repo_root / "src" / "quantumvitas" / "cli"
    
    if not cli_dir.exists():
        print(f"Error: CLI directory not found: {cli_dir}", file=sys.stderr)
        sys.exit(1)
    
    manifest = audit_cli_imports(cli_dir)
    
    # Output JSON to stdout
    json_output = json.dumps(manifest, indent=2)
    print(json_output)
    
    # Optionally save to file
    if args.json:
        output_file = Path(args.json)
        output_file.write_text(json_output, encoding="utf-8")
        print(f"\nManifest also saved to: {output_file}", file=sys.stderr)


if __name__ == "__main__":
    main()

