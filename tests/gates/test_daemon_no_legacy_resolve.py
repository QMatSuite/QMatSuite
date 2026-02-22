"""
Gate test: Daemon must not use legacy svc.resolve_* methods.

This test ensures daemon code uses domain methods only:
- svc.calculation.require_ref() instead of svc.resolve_calculation_ref()
- svc.structure.require_ref() instead of svc.resolve_structure_ref()

Forbidden patterns:
- ".resolve_calculation_ref"
- ".resolve_structure_ref"
- "svc.resolve_" (any top-level resolve method on svc)
"""

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
DAEMON_DIR = PROJECT_ROOT / "src" / "qmatsuite" / "daemon"


def test_daemon_no_legacy_resolve_methods():
    """
    Ensure daemon code does not use legacy svc.resolve_* methods.
    
    Forbidden patterns:
    - .resolve_calculation_ref
    - .resolve_structure_ref
    - svc.resolve_* (any top-level resolve method)
    
    Allowed patterns:
    - svc.calculation.require_ref()
    - svc.structure.require_ref()
    - Other domain methods
    """
    violations = []
    
    # Scan all Python files in daemon directory
    for py_file in DAEMON_DIR.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
            
        try:
            content = py_file.read_text(encoding="utf-8")
            lines = content.splitlines()
            
            # Check for forbidden patterns
            import re
            for line_num, line in enumerate(lines, start=1):
                # Check for .resolve_calculation_ref
                if ".resolve_calculation_ref" in line:
                    violations.append((py_file, line_num, line, ".resolve_calculation_ref"))
                
                # Check for .resolve_structure_ref
                if ".resolve_structure_ref" in line:
                    violations.append((py_file, line_num, line, ".resolve_structure_ref"))
                
                # Check for .resolve_step_ref
                if ".resolve_step_ref" in line:
                    violations.append((py_file, line_num, line, ".resolve_step_ref"))
                
                # Check for svc.resolve_* (top-level resolve methods)
                # Be careful to avoid false positives like "svc.calculation.resolve_enclosing_path"
                # Pattern: "svc.resolve_" followed by word characters (not a dot)
                if re.search(r'\bsvc\.resolve_\w+', line):
                    # Allow if it's part of a domain method like "svc.calculation.resolve_"
                    if not re.search(r'svc\.\w+\.resolve_', line):
                        violations.append((py_file, line_num, line, "svc.resolve_*"))
        
        except Exception as e:
            pytest.fail(f"Error reading {py_file}: {e}")
    
    if violations:
        # Build error message
        lines = [
            "\n" + "="*70,
            "DAEMON LEGACY RESOLVE METHODS DETECTED:",
            "="*70,
            "",
            f"Found {len(violations)} violation(s). Daemon must use domain methods only.",
            "",
            "Forbidden patterns:",
            "  - .resolve_calculation_ref",
            "  - .resolve_structure_ref",
            "  - .resolve_step_ref",
            "  - svc.resolve_* (any top-level resolve method)",
            "",
            "Use instead:",
            "  - svc.calculation.require_ref(selector)",
            "  - svc.structure.require_ref(selector)",
            "  - svc.calculation.require_step_ref(calc_selector, step_selector)",
            "  - Or use daemon helper: _require_calculation_ref(svc, selector)",
            "  - Or use daemon helper: _require_structure_ref(svc, selector)",
            "  - Or use daemon helper: _require_step_ref(svc, calc_selector, step_selector)",
            "",
            "Violations:",
        ]
        
        for py_file, line_num, line_content, pattern in violations:
            rel_path = py_file.relative_to(PROJECT_ROOT)
            # Strip leading whitespace for display
            line_stripped = line_content.strip()
            lines.append(f"  {rel_path}:{line_num}")
            lines.append(f"    Pattern: {pattern}")
            lines.append(f"    Line: {line_stripped}")
            lines.append("")
        
        lines.append("="*70)
        error_msg = "\n".join(lines)
        pytest.fail(error_msg)

