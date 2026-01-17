"""
Guard test: Ensure deprecated StepTypeSpec preset fields are removed.

This test fails if any production code references:
- StepTypeSpec.accepts_presets
- StepTypeSpec.allowed_dimensions
- list_accepting_presets() method
- PW_DIMENSIONS constant
"""

import pytest
import subprocess


def test_no_accepts_presets_in_production_code():
    """Production code must not reference accepts_presets field."""
    result = subprocess.run(
        ["rg", "-l", r"\.accepts_presets", "src/quantumvitas"],
        capture_output=True,
        text=True,
    )
    matching_files = result.stdout.strip()
    assert not matching_files, (
        f"Found accepts_presets field reference in production code:\n{matching_files}"
    )


def test_no_allowed_dimensions_in_production_code():
    """Production code must not reference allowed_dimensions field."""
    result = subprocess.run(
        ["rg", "-l", r"\.allowed_dimensions", "src/quantumvitas"],
        capture_output=True,
        text=True,
    )
    matching_files = result.stdout.strip()
    assert not matching_files, (
        f"Found allowed_dimensions field reference in production code:\n{matching_files}"
    )


def test_no_pw_dimensions_in_production_code():
    """Production code must not reference PW_DIMENSIONS constant."""
    result = subprocess.run(
        ["rg", "-l", r"PW_DIMENSIONS", "src/quantumvitas"],
        capture_output=True,
        text=True,
    )
    matching_files = result.stdout.strip()
    assert not matching_files, (
        f"Found PW_DIMENSIONS constant reference in production code:\n{matching_files}"
    )


def test_no_deprecated_list_accepting_presets():
    """Production code must not have deprecated list_accepting_presets() method."""
    result = subprocess.run(
        ["rg", "-l", r"def list_accepting_presets\(self\)", "src/quantumvitas"],
        capture_output=True,
        text=True,
    )
    matching_files = result.stdout.strip()
    assert not matching_files, (
        f"Found deprecated list_accepting_presets() method:\n{matching_files}"
    )


def test_steptypespec_has_no_preset_fields():
    """StepTypeSpec dataclass must not have preset-related fields."""
    from quantumvitas.workflow.registry import StepTypeSpec
    import dataclasses
    
    field_names = [f.name for f in dataclasses.fields(StepTypeSpec)]
    
    assert "accepts_presets" not in field_names, (
        "StepTypeSpec still has accepts_presets field"
    )
    assert "allowed_dimensions" not in field_names, (
        "StepTypeSpec still has allowed_dimensions field"
    )


def test_registry_has_no_deprecated_method():
    """StepTypeRegistry must not have deprecated list_accepting_presets() method."""
    from quantumvitas.workflow.registry import StepTypeRegistry
    
    assert not hasattr(StepTypeRegistry, "list_accepting_presets"), (
        "StepTypeRegistry still has deprecated list_accepting_presets() method"
    )

