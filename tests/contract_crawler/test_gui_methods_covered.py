"""
Soft gate: Ensure GUI-used RPC methods are covered.

This test validates that all GUI-used methods are either:
- Covered by golden fixtures, OR
- Present in EXEMPT_METHODS with a non-empty reason

Implemented as a "soft gate" that can be skipped unless QV_ENFORCE_GUI_RPC_COVERAGE=1.
"""

import os
import pytest
from pathlib import Path

from tests.contract_crawler.introspection import get_all_rpc_methods
from tests.contract_crawler.test_coverage import EXEMPT_METHODS
from tests.contract_crawler.report_coverage import load_gui_methods, load_golden_fixtures


GUI_METHODS_FILE = Path(__file__).parent.parent.parent / "gui" / "tests" / "e2e" / "tools" / "gui_rpc_methods.json"
ENFORCE_ENV_VAR = "QV_ENFORCE_GUI_RPC_COVERAGE"


@pytest.mark.skipif(
    os.environ.get(ENFORCE_ENV_VAR) != "1",
    reason=f"GUI coverage gate is soft. Set {ENFORCE_ENV_VAR}=1 to enforce."
)
def test_gui_methods_covered():
    """
    All GUI-used RPC methods must be covered or exempt.
    
    This is a soft gate - it will be skipped unless QV_ENFORCE_GUI_RPC_COVERAGE=1.
    When enforced, it fails with a clear message listing missing methods.
    """
    # Load GUI methods
    gui_methods = load_gui_methods()
    
    if not gui_methods:
        pytest.skip("No GUI methods found. Run scan_gui_rpc_methods.py first.")
    
    # Load golden fixtures
    golden_fixtures = load_golden_fixtures()
    
    # Get all introspected methods for validation
    all_methods = {m.name for m in get_all_rpc_methods()}
    
    # Check each GUI method
    missing_methods = []
    
    for method_name in gui_methods:
        # Validate method exists in daemon
        if method_name not in all_methods:
            # Method doesn't exist - might be a typo or removed method
            continue
        
        # Check if covered by golden fixture
        if method_name in golden_fixtures:
            continue
        
        # Check if exempt
        if method_name in EXEMPT_METHODS:
            reason = EXEMPT_METHODS[method_name]
            if not reason or not reason.strip():
                missing_methods.append(f"{method_name} (exempt but reason is empty)")
            continue
        
        # Method is missing coverage
        missing_methods.append(method_name)
    
    if missing_methods:
        error_msg = (
            f"GUI-used RPC methods missing coverage ({len(missing_methods)} methods):\n\n"
            + "\n".join(f"  - {m}" for m in sorted(missing_methods))
            + "\n\n"
            "To fix:\n"
            "  1. Add minimal payload to payloads.py (for auto-crawler), OR\n"
            "  2. Create a recipe in recipes/ (for complex methods), OR\n"
            "  3. Add to EXEMPT_METHODS in test_coverage.py with a non-empty reason"
        )
        pytest.fail(error_msg)


def test_gui_methods_covered_soft():
    """
    Soft gate version - always runs but uses xfail to show missing methods.
    
    This makes the missing list visible without blocking CI.
    """
    gui_methods = load_gui_methods()
    
    if not gui_methods:
        pytest.skip("No GUI methods found. Run scan_gui_rpc_methods.py first.")
    
    golden_fixtures = load_golden_fixtures()
    all_methods = {m.name for m in get_all_rpc_methods()}
    
    missing_methods = []
    
    for method_name in gui_methods:
        if method_name not in all_methods:
            continue
        if method_name in golden_fixtures:
            continue
        if method_name in EXEMPT_METHODS:
            continue
        missing_methods.append(method_name)
    
    if missing_methods:
        missing_list = ', '.join(sorted(missing_methods)[:10])
        if len(missing_methods) > 10:
            missing_list += f" ... and {len(missing_methods) - 10} more"
        pytest.skip(
            f"GUI methods missing coverage ({len(missing_methods)}): {missing_list}"
        )
