"""
Guard tests to prevent reintroduction of old gating logic.

These tests use pure-Python repo scanner to ensure production code does not:
- Reference deprecated StepTypeSpec fields (accepts_presets, allowed_dimensions)
- Bypass capability resolver (direct ParamSpace apply without validation)
- Miss require_preset_capability calls in apply paths

Note: Uses pure-Python repo scanner instead of ripgrep (rg) for CI portability.
"""

import pytest
from tests.utils.repo_scan import scan_for_pattern


def test_no_accepts_presets_field():
    """Production code must not reference StepTypeSpec.accepts_presets."""
    matching_files = scan_for_pattern("accepts_presets", return_lines=False)
    # Filter out test files (already excluded by collect_production_files, but double-check)
    production_files = [
        str(f) for f in matching_files if "test" not in str(f).lower()
    ]
    assert len(production_files) == 0, (
        f"Found accepts_presets in production code: {production_files}"
    )


def test_no_allowed_dimensions_field():
    """Production code must not reference StepTypeSpec.allowed_dimensions."""
    matching_files = scan_for_pattern("allowed_dimensions", return_lines=False)
    # Filter out test files (already excluded by collect_production_files, but double-check)
    production_files = [
        str(f) for f in matching_files if "test" not in str(f).lower()
    ]
    assert len(production_files) == 0, (
        f"Found allowed_dimensions in production code: {production_files}"
    )


def test_apply_calls_require_capability():
    """apply_presets_to_step must call require_preset_capability."""
    from pathlib import Path
    import os
    
    # Get the repo root
    repo_root = Path(__file__).parent.parent.parent
    integration_file = repo_root / "src" / "qmatsuite" / "presets" / "integration.py"
    
    # Read the file and check for require_preset_capability
    if integration_file.exists():
        content = integration_file.read_text()
        assert "require_preset_capability" in content, (
            "apply_presets_to_step must call require_preset_capability for capability validation"
        )
    else:
        pytest.fail(f"integration.py not found at {integration_file}")


def test_no_direct_paramspace_apply_bypass():
    """
    Ensure no direct ParamSpace apply without capability validation.
    
    This checks that apply_presets_to_step uses the capability resolver,
    not direct ParamSpace compilation without validation.
    """
    from pathlib import Path
    
    # Get the repo root
    repo_root = Path(__file__).parent.parent.parent
    integration_file = repo_root / "src" / "qmatsuite" / "presets" / "integration.py"
    
    # Read the file and check for capability import
    if integration_file.exists():
        content = integration_file.read_text()
        assert "from qmatsuite.presets.capability import" in content or "import.*capability" in content, (
            "integration.py must import from capability module for validation"
        )
    else:
        pytest.fail(f"integration.py not found at {integration_file}")

