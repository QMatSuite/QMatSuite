"""
Guard test: Ensure deprecated StepTypeSpec preset fields are removed.

This test fails if any production code references:
- StepTypeSpec.accepts_presets
- StepTypeSpec.allowed_dimensions
- list_accepting_presets() method
- PW_DIMENSIONS constant

Note: Uses pure-Python repo scanner instead of ripgrep (rg) for CI portability.
"""

import pytest
from tests.utils.repo_scan import scan_for_pattern_list_files


def test_no_accepts_presets_in_production_code():
    """Production code must not reference accepts_presets field."""
    matching_files = scan_for_pattern_list_files(r"\.accepts_presets")
    assert not matching_files, (
        f"Found accepts_presets field reference in production code:\n{matching_files}"
    )


def test_no_allowed_dimensions_in_production_code():
    """Production code must not reference allowed_dimensions field."""
    matching_files = scan_for_pattern_list_files(r"\.allowed_dimensions")
    assert not matching_files, (
        f"Found allowed_dimensions field reference in production code:\n{matching_files}"
    )


def test_no_pw_dimensions_in_production_code():
    """Production code must not reference PW_DIMENSIONS constant."""
    matching_files = scan_for_pattern_list_files(r"PW_DIMENSIONS")
    assert not matching_files, (
        f"Found PW_DIMENSIONS constant reference in production code:\n{matching_files}"
    )


def test_no_deprecated_list_accepting_presets():
    """Production code must not have deprecated list_accepting_presets() method."""
    matching_files = scan_for_pattern_list_files(r"def list_accepting_presets\(self\)")
    assert not matching_files, (
        f"Found deprecated list_accepting_presets() method:\n{matching_files}"
    )


def test_steptypespec_has_no_preset_fields():
    """StepTypeSpec dataclass must not have preset-related fields."""
    from qmatsuite.workflow.registry import StepTypeSpec
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
    from qmatsuite.workflow.registry import StepTypeRegistry
    
    assert not hasattr(StepTypeRegistry, "list_accepting_presets"), (
        "StepTypeRegistry still has deprecated list_accepting_presets() method"
    )

