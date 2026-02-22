#!/usr/bin/env python3
"""
Audit daemon kernel imports to generate a dependency manifest.

Scans src/qmatsuite/daemon/server.py using AST and reports all forbidden
imports (qmatsuite.core, qmatsuite.calculation, qmatsuite.analysis,
qmatsuite.io, qmatsuite.drivers).

Outputs JSON manifest with:
- Total violations
- By module (grouped by imported module)
- By symbol (grouped by imported symbol)
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
    "qmatsuite.core",
    "qmatsuite.calculation",
    "qmatsuite.analysis",
    "qmatsuite.io",
    "qmatsuite.drivers",
    "qmatsuite.engine",
    "qmatsuite.workflow",
    "qmatsuite.presets",
)


class ImportVisitor(ast.NodeVisitor):
    """AST visitor to collect forbidden imports with function context."""
    
    def __init__(self):
        self.violations: List[Dict[str, Any]] = []
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


def audit_daemon_imports(daemon_file: Path) -> Dict[str, Any]:
    """
    Audit daemon file for forbidden kernel imports.
    
    Args:
        daemon_file: Path to daemon server.py file
        
    Returns:
        JSON-serializable manifest dict
    """
    try:
        content = daemon_file.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(daemon_file))
    except SyntaxError as e:
        print(f"Warning: Syntax error in {daemon_file}: {e}", file=sys.stderr)
        return {
            "file": str(daemon_file),
            "total_violations": 0,
            "by_module": {},
            "by_symbol": {},
            "error": str(e),
        }
    except Exception as e:
        print(f"Warning: Error reading {daemon_file}: {e}", file=sys.stderr)
        return {
            "file": str(daemon_file),
            "total_violations": 0,
            "by_module": {},
            "by_symbol": {},
            "error": str(e),
        }
    
    visitor = ImportVisitor()
    visitor.visit(tree)
    
    # Build statistics
    by_module: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"count": 0, "lines": [], "functions": set(), "files": set()})
    by_symbol: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"count": 0, "lines": [], "functions": set(), "files": set()})
    
    file_path_str = str(daemon_file.relative_to(daemon_file.parent.parent.parent.parent))
    
    for violation in visitor.violations:
        module = violation["module"]
        symbol = violation["symbol"]
        line = violation["line"]
        func = violation["function"]
        
        # By module
        by_module[module]["count"] += 1
        by_module[module]["lines"].append(line)
        by_module[module]["files"].add(file_path_str)
        if func:
            by_module[module]["functions"].add(func)
        
        # By symbol (if symbol exists)
        if symbol:
            symbol_key = f"{module}:{symbol}"
            by_symbol[symbol_key]["count"] += 1
            by_symbol[symbol_key]["lines"].append(line)
            by_symbol[symbol_key]["files"].add(file_path_str)
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
    
    return {
        "daemon_file": str(daemon_file),
        "total_violations": len(visitor.violations),
        "by_module": by_module_sorted,
        "by_symbol": by_symbol_sorted,
    }


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Audit daemon kernel imports")
    parser.add_argument("--json", type=str, help="Output JSON to file (default: ./.audit/daemon_kernel_deps.json)")
    args = parser.parse_args()
    
    repo_root = Path(__file__).parent.parent
    daemon_file = repo_root / "src" / "qmatsuite" / "daemon" / "server.py"
    
    if not daemon_file.exists():
        print(f"Error: Daemon file not found: {daemon_file}", file=sys.stderr)
        sys.exit(1)
    
    manifest = audit_daemon_imports(daemon_file)
    
    # Determine output file (default to .audit/ directory)
    if args.json:
        output_file = Path(args.json)
    else:
        # Default: ./.audit/daemon_kernel_deps.json
        audit_dir = repo_root / ".audit"
        audit_dir.mkdir(exist_ok=True)
        output_file = audit_dir / "daemon_kernel_deps.json"
    
    # Save to file
    json_output = json.dumps(manifest, indent=2)
    output_file.write_text(json_output, encoding="utf-8")
    print(f"Manifest saved to: {output_file}", file=sys.stderr)
    
    # Also output to stdout
    print(json_output)


if __name__ == "__main__":
    main()

