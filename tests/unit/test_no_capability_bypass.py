"""
Guard tests to prevent reintroduction of old gating logic.

These tests use grep/ripgrep to ensure production code does not:
- Reference deprecated StepTypeSpec fields (accepts_presets, allowed_dimensions)
- Bypass capability resolver (direct ParamSpace apply without validation)
- Miss require_preset_capability calls in apply paths
"""

import subprocess
import pytest


def test_no_accepts_presets_field():
    """Production code must not reference StepTypeSpec.accepts_presets."""
    result = subprocess.run(
        ["rg", "accepts_presets", "src/quantumvitas", "--type", "py", "-l"],
        capture_output=True,
        text=True,
    )
    # Filter out test files
    production_files = [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip() and "test" not in line.lower()
    ]
    assert len(production_files) == 0, (
        f"Found accepts_presets in production code: {production_files}"
    )


def test_no_allowed_dimensions_field():
    """Production code must not reference StepTypeSpec.allowed_dimensions."""
    result = subprocess.run(
        ["rg", "allowed_dimensions", "src/quantumvitas", "--type", "py", "-l"],
        capture_output=True,
        text=True,
    )
    # Filter out test files
    production_files = [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip() and "test" not in line.lower()
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
    integration_file = repo_root / "src" / "quantumvitas" / "presets" / "integration.py"
    
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
    integration_file = repo_root / "src" / "quantumvitas" / "presets" / "integration.py"
    
    # Read the file and check for capability import
    if integration_file.exists():
        content = integration_file.read_text()
        assert "from quantumvitas.presets.capability import" in content or "import.*capability" in content, (
            "integration.py must import from capability module for validation"
        )
    else:
        pytest.fail(f"integration.py not found at {integration_file}")

