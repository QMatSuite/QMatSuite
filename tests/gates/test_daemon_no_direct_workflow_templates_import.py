"""
Gate test: daemon must not import workflow.templates directly.

The daemon should use QVService.get_workflow_service() instead of
directly importing from quantumvitas.workflow.templates.

This ensures the daemon stays behind the API facade and maintains
architectural boundaries.
"""

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
DAEMON_FILE = PROJECT_ROOT / "src/quantumvitas/daemon/server.py"


def test_daemon_no_direct_workflow_templates_import():
    """
    Verify daemon/server.py does not import workflow.templates directly.
    
    Allowed:
    - Comments containing "workflow.templates"
    - Docstrings containing "workflow.templates"
    - QVService.get_workflow_service() calls (method calls, not imports)
    
    Forbidden:
    - import quantumvitas.workflow.templates
    - from quantumvitas.workflow.templates import ...
    """
    if not DAEMON_FILE.exists():
        pytest.skip(f"Daemon file not found: {DAEMON_FILE}")
    
    violations = []
    lines = DAEMON_FILE.read_text(encoding="utf-8").splitlines()
    
    # Patterns to detect forbidden imports
    forbidden_patterns = [
        # Direct import
        (r'^\s*import\s+quantumvitas\.workflow\.templates', "Direct import of quantumvitas.workflow.templates"),
        # From import
        (r'^\s*from\s+quantumvitas\.workflow\.templates\s+import', "From import of quantumvitas.workflow.templates"),
    ]
    
    in_docstring = False
    docstring_delimiter = None
    
    for line_num, line in enumerate(lines, start=1):
        stripped = line.strip()
        
        # Track docstrings (simple heuristic: look for triple quotes)
        if stripped.startswith('"""') or stripped.startswith("'''"):
            if in_docstring:
                # Closing docstring
                if stripped.endswith('"""') or stripped.endswith("'''"):
                    in_docstring = False
                    docstring_delimiter = None
            else:
                # Opening docstring
                if stripped.endswith('"""') or stripped.endswith("'''"):
                    # Single-line docstring, skip
                    continue
                else:
                    in_docstring = True
                    docstring_delimiter = stripped[:3]
                    continue
        
        if in_docstring:
            # Check if we're closing the docstring
            if docstring_delimiter and docstring_delimiter in stripped:
                in_docstring = False
                docstring_delimiter = None
            continue
        
        # Skip comments
        if stripped.startswith('#'):
            continue
        
        # Check for forbidden patterns
        for pattern, description in forbidden_patterns:
            if re.search(pattern, line):
                violations.append(
                    f"{DAEMON_FILE}:{line_num}: {description}\n"
                    f"  Line: {line.strip()}"
                )
    
    if violations:
        report = "\n".join([
            "=" * 70,
            "Daemon: Forbidden direct import of workflow.templates",
            "=" * 70,
            "",
            f"Found {len(violations)} violation(s):",
            "",
        ] + violations + [
            "",
            "=" * 70,
            "Fix: Use QVService.get_workflow_service() instead of",
            "     directly importing from quantumvitas.workflow.templates",
            "=" * 70,
        ])
        pytest.fail(report)

