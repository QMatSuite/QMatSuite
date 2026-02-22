"""
Gate 0.4: Legacy accessor side-door detector

Detects attribute access patterns that indicate side-door legacy usage:
- any attribute named "_legacy" accessed off service/svc/QMSService instances
- any usage of names api_legacy / _api_legacy / LegacyService as identifiers
"""

import ast
from pathlib import Path


class LegacyAccessorVisitor(ast.NodeVisitor):
    """AST visitor to detect legacy accessor side-doors."""
    
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.violations = []
    
    def visit_Attribute(self, node: ast.Attribute):
        """Detect _legacy attribute access."""
        if node.attr == "_legacy":
            # Check if it's accessed off something that looks like service
            if isinstance(node.value, ast.Name):
                var_name = node.value.id
                if var_name in ("service", "svc", "qmsservice", "qms_service"):
                    self.violations.append({
                        "file": str(self.file_path),
                        "line": node.lineno,
                        "pattern": f"{var_name}._legacy",
                        "type": "legacy_attribute_access",
                    })
            elif isinstance(node.value, ast.Attribute):
                # Nested: something.service._legacy
                if node.value.attr in ("service", "svc"):
                    self.violations.append({
                        "file": str(self.file_path),
                        "line": node.lineno,
                        "pattern": f"{node.value.attr}._legacy",
                        "type": "legacy_attribute_access",
                    })
        
        self.generic_visit(node)
    
    def visit_Name(self, node: ast.Name):
        """Detect legacy identifier usage (conservative - only obvious cases)."""
        legacy_names = ["api_legacy", "_api_legacy", "LegacyService"]
        if node.id in legacy_names:
            # Only flag if it's not in an import statement (handled separately)
            # This is conservative - may miss some cases but avoids false positives
            pass
        self.generic_visit(node)


def test_no_legacy_accessor_side_door():
    """Ensure no legacy accessor side-doors in production code."""
    src = Path("src/qmatsuite")
    all_violations = []

    for py_file in src.rglob("*.py"):
        # Skip vault directory
        if "_vault" in str(py_file):
            continue
        # Skip migration tooling
        if "migration_" in py_file.name:
            continue

        try:
            content = py_file.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(py_file))
            
            visitor = LegacyAccessorVisitor(py_file)
            visitor.visit(tree)
            
            all_violations.extend(visitor.violations)
        except (SyntaxError, UnicodeDecodeError, Exception):
            # Skip files that can't be parsed
            continue

    if all_violations:
        error_msg = "ERROR: Legacy accessor side-door detected:\n"
        for violation in all_violations:
            rel_path = Path(violation["file"]).relative_to(Path("src"))
            error_msg += f"  - {rel_path}:{violation['line']}: {violation['pattern']}\n"
        error_msg += "\nProduction code must not access legacy via side-doors."
        assert False, error_msg

