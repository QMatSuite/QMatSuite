"""
Guard test: Ensure StepType enum is not used in production code.

SSOT: Only gen/public step (string) and spec/machine step (string) are allowed.
"""

import subprocess
import pytest


def test_no_steptype_import_in_production():
    """Production code must not import StepType."""
    result = subprocess.run(
        ["rg", "-l", r"from.*StepType|import.*StepType", "src/quantumvitas"],
        capture_output=True,
        text=True,
    )
    matching_files = result.stdout.strip()
    # Filter out types.py where StepMode/StepStatus are defined
    if matching_files:
        files = [f for f in matching_files.split('\n') if 'types.py' not in f]
        matching_files = '\n'.join(files)
    assert not matching_files, (
        f"Found StepType import in production code:\n{matching_files}\n\n"
        "SSOT violation: Use gen/public step (str) or spec/machine step (str) instead."
    )


def test_no_steptype_enum_definition():
    """StepType enum must not exist in types.py."""
    result = subprocess.run(
        ["rg", "-l", r"class StepType", "src/quantumvitas"],
        capture_output=True,
        text=True,
    )
    matching_files = result.stdout.strip()
    assert not matching_files, (
        f"Found StepType enum definition:\n{matching_files}\n\n"
        "SSOT violation: StepType enum must be deleted."
    )


def test_no_coerce_step_type_function():
    """_coerce_step_type must not exist."""
    result = subprocess.run(
        ["rg", "-l", r"def _coerce_step_type", "src/quantumvitas"],
        capture_output=True,
        text=True,
    )
    matching_files = result.stdout.strip()
    assert not matching_files, (
        f"Found _coerce_step_type function:\n{matching_files}\n\n"
        "This function is deprecated; use strings directly."
    )

