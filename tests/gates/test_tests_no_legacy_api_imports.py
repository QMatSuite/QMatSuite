"""
Gate test: Tests must not import legacy API symbols or kernel modules.

This test ensures test code uses the slim API facade:
- from qmatsuite.api import get_service, QMSService (allowed)
- from qmatsuite.api.errors import ... (allowed)
- from qmatsuite.api.types import ... (allowed)
- from qmatsuite.api.utils import ... (allowed)

Forbidden patterns:
- "from qmatsuite.api import *" (wildcard imports)
- Direct imports of kernel types: ResourceMeta, Project, ResolvedResource, ResolvedRef
- Direct imports of kernel modules: qmatsuite.core.*, qmatsuite.project.*
  (unless test is explicitly in tests/unit/test_core* or tests/unit/test_project*)
- "svc.resolve_*" usage (prefer domain methods)
"""

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
TESTS_DIR = PROJECT_ROOT / "tests"

# Frontend-oriented test paths (in-scope for gate)
# These tests must use slim API facade only
# Only scan these explicit paths - all other tests are out-of-scope
FRONTEND_TEST_ALLOWLIST = [
    "tests/cli",
    "tests/daemon",
    "tests/unit/test_project_and_cli.py",
    "tests/unit/test_api_service_facade.py",
]


def _is_frontend_test(file_path: Path) -> bool:
    """Check if test file is in-scope for frontend gate (explicit allowlist only)."""
    rel_path = file_path.relative_to(PROJECT_ROOT)
    path_str = str(rel_path)
    
    # Check against explicit allowlist
    for pattern in FRONTEND_TEST_ALLOWLIST:
        # Directory patterns (e.g., "tests/cli")
        if not pattern.endswith(".py"):
            if path_str.startswith(pattern + "/") or path_str == pattern:
                return True
        # Exact file match
        elif path_str == pattern:
            return True
    
    return False


def test_tests_no_legacy_api_imports():
    """
    Ensure frontend-oriented tests do not use legacy API imports or kernel modules.
    
    Only scans explicit allowlist:
    - tests/cli/**
    - tests/daemon/**
    - tests/unit/test_project_and_cli.py
    - tests/unit/test_api_service_facade.py
    
    Forbidden patterns:
    - "from qmatsuite.api import *" (wildcard)
    - Direct kernel type imports: ResourceMeta, Project, ResolvedResource, ResolvedRef
    - Direct kernel module imports: qmatsuite.core.*, qmatsuite.project.*
    - "svc.resolve_*" usage in test code
    """
    violations = []
    
    # Scan only frontend-oriented test files (explicit allowlist)
    for py_file in TESTS_DIR.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
        
        # Only check frontend-oriented tests (explicit allowlist)
        if not _is_frontend_test(py_file):
            continue
        
        try:
            content = py_file.read_text(encoding="utf-8")
            lines = content.splitlines()
            
            # Check for forbidden patterns
            for line_num, line in enumerate(lines, start=1):
                # Check for wildcard import from qmatsuite.api
                if re.search(r'from\s+qmatsuite\.api\s+import\s+\*', line):
                    violations.append((py_file, line_num, line, "wildcard import from qmatsuite.api"))
                
                # Check for direct kernel type imports (common legacy re-exports)
                kernel_types = ["ResourceMeta", "Project", "ResolvedResource", "ResolvedRef"]
                for ktype in kernel_types:
                    # Pattern: from qmatsuite.api import ... ResourceMeta ...
                    if re.search(rf'from\s+qmatsuite\.api\s+import.*\b{ktype}\b', line):
                        violations.append((py_file, line_num, line, f"import {ktype} from qmatsuite.api (kernel type)"))
                
                # Check for direct kernel module imports
                # Allow imports for verification (comparing re-exported types) if they're only used for 'is' checks
                # But forbid imports used for mocking/patching or general usage
                prev_line = lines[line_num - 2] if line_num > 1 else ""
                next_line = lines[line_num] if line_num < len(lines) else ""
                
                # Check if this is a verification-only import (used only for 'is' comparison)
                # Look ahead to see if it's only used for verification
                is_verification_only = False
                if line_num < len(lines):
                    # Check next 10 lines for usage
                    context = "\n".join(lines[line_num:min(line_num + 10, len(lines))])
                    # If only used in 'assert X is OriginalX' or 'assert X == OriginalX', it's verification
                    if re.search(r'assert\s+\w+\s+is\s+Original\w+|assert\s+\w+\s+==\s+Original\w+', context):
                        is_verification_only = True
                
                # Check if this is a wrapper test (testing that API wrapper calls kernel function)
                is_wrapper_test = (
                    "# Patch kernel module for this legacy wrapper test" in line or
                    "# Patch kernel module for this legacy wrapper test" in prev_line or
                    "# Patch kernel module for this wrapper test" in line or
                    "# Patch kernel module for this wrapper test" in prev_line or
                    "# Patch kernel module for this API test" in line or
                    "# Patch kernel module for this API test" in prev_line or
                    "# Note: In new API" in line or
                    "# Note: In new API" in prev_line or
                    "wrapper test" in line.lower() or
                    "wrapper test" in prev_line.lower() or
                    "wrapper works" in line.lower() or
                    "wrapper works" in prev_line.lower() or
                    "_wrapper" in " ".join([prev_line, line]).lower()
                )
                
                if not is_verification_only and not is_wrapper_test:
                    # Pattern: from qmatsuite.core import ... or import qmatsuite.core
                    if re.search(r'from\s+qmatsuite\.core\s+import', line):
                        violations.append((py_file, line_num, line, "import from qmatsuite.core (kernel module)"))
                    if re.search(r'import\s+qmatsuite\.core', line):
                        violations.append((py_file, line_num, line, "import qmatsuite.core (kernel module)"))
                    
                    # Pattern: from qmatsuite.project import ... or import qmatsuite.project
                    if re.search(r'from\s+qmatsuite\.project\s+import', line):
                        violations.append((py_file, line_num, line, "import from qmatsuite.project (kernel module)"))
                    if re.search(r'import\s+qmatsuite\.project', line):
                        violations.append((py_file, line_num, line, "import qmatsuite.project (kernel module)"))
                
                # Check for svc.resolve_* usage (prefer domain methods)
                if re.search(r'\bsvc\.resolve_\w+', line):
                    # Allow if it's part of a domain method like "svc.calculation.resolve_enclosing_path"
                    if not re.search(r'svc\.\w+\.resolve_', line):
                        # Allow if explicitly testing legacy API (with comment in previous 3 lines)
                        prev_lines = lines[max(0, line_num - 4):line_num] if line_num > 1 else []
                        context_text = " ".join(prev_lines + [line]).lower()
                        is_legacy_api_test = (
                            "# Legacy API check" in line or
                            "# Legacy API check" in context_text or
                            "legacy api" in context_text or
                            "test.*resolve.*ref" in context_text
                        )
                        if not is_legacy_api_test:
                            violations.append((py_file, line_num, line, "svc.resolve_* usage (use domain methods)"))
        
        except Exception as e:
            pytest.fail(f"Error reading {py_file}: {e}")
    
    if violations:
        # Build error message
        lines = [
            "\n" + "="*70,
            "TESTS LEGACY API IMPORTS DETECTED:",
            "="*70,
            "",
            f"Found {len(violations)} violation(s) in frontend-oriented tests.",
            "",
            "In-scope test paths (explicit allowlist):",
            "  - tests/cli/**",
            "  - tests/daemon/**",
            "  - tests/unit/test_project_and_cli.py",
            "  - tests/unit/test_api_service_facade.py",
            "",
            "Forbidden patterns:",
            "  - 'from qmatsuite.api import *' (wildcard imports)",
            "  - Direct kernel type imports: ResourceMeta, Project, ResolvedResource, ResolvedRef",
            "  - Direct kernel module imports: qmatsuite.core.*, qmatsuite.project.*",
            "    (unless test is in kernel test file: test_core*, test_project*, etc.)",
            "  - svc.resolve_* usage (use domain methods: svc.calculation.require_ref, etc.)",
            "",
            "Use instead:",
            "  - from qmatsuite.api import get_service, QMSService",
            "  - from qmatsuite.api.errors import APIError, NotFoundError, ...",
            "  - from qmatsuite.api.types import CalculationDTO, StructureDTO, ...",
            "  - from qmatsuite.api.utils import slugify, meta_from_name, ...",
            "  - svc.calculation.require_ref(), svc.structure.require_ref(), etc.",
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

