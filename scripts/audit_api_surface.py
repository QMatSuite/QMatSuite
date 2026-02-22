#!/usr/bin/env python3
"""
Audit API facade surface to generate inventory and classification.

Analyzes src/qmatsuite/api.py to:
- Count QMSService instance methods
- Count QMSService static methods
- List module-level re-exports
- Classify by category
"""

import ast
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

def analyze_api_surface(api_file: Path) -> Dict[str, Any]:
    """Analyze API facade surface."""
    content = api_file.read_text(encoding="utf-8")
    tree = ast.parse(content, filename=str(api_file))
    
    # Find QMSService class
    qmsservice_class = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "QMSService":
            qmsservice_class = node
            break
    
    if not qmsservice_class:
        return {"error": "QMSService class not found"}
    
    # Collect methods
    instance_methods = []
    static_methods = []
    
    for node in qmsservice_class.body:
        if isinstance(node, ast.FunctionDef):
            # Check if staticmethod
            is_static = False
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Name) and decorator.id == "staticmethod":
                    is_static = True
                    break
                elif isinstance(decorator, ast.Name) and decorator.id == "classmethod":
                    is_static = True
                    break
            
            if is_static:
                static_methods.append(node.name)
            else:
                if node.name != "__init__":
                    instance_methods.append(node.name)
    
    # Find __all__ exports
    all_exports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    if isinstance(node.value, ast.List):
                        for elt in node.value.elts:
                            if isinstance(elt, ast.Constant):
                                all_exports.append(elt.value)
    
    # Find re-export imports (from X import Y)
    re_exports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("qmatsuite."):
                for alias in node.names:
                    if alias.name != "*":
                        re_exports.append({
                            "symbol": alias.name,
                            "from": node.module,
                            "asname": alias.asname or alias.name,
                        })
    
    return {
        "instance_methods": sorted(instance_methods),
        "static_methods": sorted(static_methods),
        "total_instance": len(instance_methods),
        "total_static": len(static_methods),
        "all_exports": sorted(all_exports),
        "total_exports": len(all_exports),
        "re_exports": re_exports,
        "total_re_exports": len(re_exports),
    }

def main():
    """Main entry point."""
    repo_root = Path(__file__).parent.parent
    api_file = repo_root / "src" / "qmatsuite" / "api.py"
    
    if not api_file.exists():
        print(f"Error: API file not found: {api_file}", file=sys.stderr)
        sys.exit(1)
    
    result = analyze_api_surface(api_file)
    
    # Output JSON
    output = json.dumps(result, indent=2)
    print(output)
    
    # Optionally save to file
    audit_dir = repo_root / ".audit"
    audit_dir.mkdir(exist_ok=True)
    output_file = audit_dir / "api_surface.json"
    output_file.write_text(output, encoding="utf-8")
    print(f"\nManifest saved to: {output_file}", file=sys.stderr)

if __name__ == "__main__":
    main()

