"""
Guard test: Ensure StepType enum is not used in production code.

SSOT: Only gen/public step (string) and spec/machine step (string) are allowed.

Note: Uses pure-Python repo scanner instead of ripgrep (rg) for CI portability.
"""

import pytest
from tests.utils.repo_scan import scan_for_pattern_list_files


def test_no_steptype_import_in_production():
    """Production code must not import StepType."""
    # Match import statements only, not comments
    # Pattern: "from ... import StepType" or "import StepType" but not StepTypeRegistry/Spec
    matching_files = scan_for_pattern_list_files(r"(?:from|import).*\bStepType\b(?!Registry|Spec)")
    # Filter out types.py where StepMode/StepStatus are defined
    if matching_files:
        files = [f for f in matching_files.split('\n') if f.strip() and 'types.py' not in f]
        matching_files = '\n'.join(files)
    assert not matching_files, (
        f"Found StepType import in production code:\n{matching_files}\n\n"
        "SSOT violation: Use gen/public step (str) or spec/machine step (str) instead."
    )


def test_no_steptype_enum_definition():
    """StepType enum must not exist in types.py."""
    # Match "class StepType" but not "class StepTypeSpec" or "class StepTypeRegistry"
    matching_files = scan_for_pattern_list_files(r"class StepType\b")
    assert not matching_files, (
        f"Found StepType enum definition:\n{matching_files}\n\n"
        "SSOT violation: StepType enum must be deleted."
    )


def test_no_coerce_step_type_function():
    """_coerce_step_type must not exist."""
    matching_files = scan_for_pattern_list_files(r"def _coerce_step_type")
    assert not matching_files, (
        f"Found _coerce_step_type function:\n{matching_files}\n\n"
        "This function is deprecated; use strings directly."
    )

