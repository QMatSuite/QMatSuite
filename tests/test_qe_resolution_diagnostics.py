"""
Test QE resolution diagnostics (two-state model).

This test verifies that QE resolution follows the two-state model:
- External QE: settings.qe.bin_dir is set (must validate pw* exists)
- Internal QE: settings.qe.bin_dir is null (auto-select from .qmatsuite/engines/qe/**/bin)
"""

import pytest
from pathlib import Path

from quantumvitas.core.engines.qe_diagnostics import (
    diagnose_qe_resolution,
    check_settings_for_external_engines,
    check_environment_variables,
    check_managed_engines,
)


def test_qe_resolution_diagnostics():
    """
    Diagnostic test: print QE resolution report (two-state model).
    
    This test does NOT fail - it's informational to help understand
    how QE is being resolved in the current environment.
    """
    # Get full diagnostic report
    report = diagnose_qe_resolution()
    settings_info = check_settings_for_external_engines()
    env_info = check_environment_variables()
    managed_info = check_managed_engines()
    
    print("\n" + "=" * 80)
    print("QE RESOLUTION DIAGNOSTICS (Two-State Model)")
    print("=" * 80)
    print(f"\nMode: {report.mode}")
    print(f"Resolution Reason: {report.resolution_reason}")
    print(f"Settings qe.bin_dir: {report.settings_bin_dir}")
    print(f"Resolved qe_bin_dir: {report.qe_bin_dir}")
    
    if report.error:
        print(f"\nError: {report.error}")
    
    print("\n--- Inputs Used ---")
    for key, value in report.inputs_used.items():
        print(f"  {key}: {value}")
    
    if report.warnings:
        print("\n--- Warnings ---")
        for warning in report.warnings:
            print(f"  ⚠️  {warning}")
    
    print("\n--- Settings.json (Two-State Model) ---")
    print(f"  Mode: {settings_info.get('mode')}")
    print(f"  qe.bin_dir: {settings_info.get('qe_bin_dir')}")
    if settings_info.get('mode') == 'external':
        print(f"  bin_dir exists: {settings_info.get('bin_dir_exists')}")
        print(f"  has pw.x: {settings_info.get('has_pw_x')}")
        print(f"  has pw.x.exe: {settings_info.get('has_pw_exe')}")
        print(f"  is_valid: {settings_info.get('is_valid')}")
    
    print("\n--- Environment Variables (Info Only) ---")
    print("  Note: Environment variables are NOT used for resolution in two-state model")
    for key, value in env_info.items():
        if value:
            print(f"  {key}: {value}")
    
    print("\n--- Internal QE Engines ---")
    print(f"  Engines Dir Exists: {managed_info.get('engines_dir_exists')}")
    print(f"  Engines Dir Path: {managed_info.get('engines_dir_path')}")
    print(f"  Managed Engines Count: {managed_info.get('managed_engines_count')}")
    for eng in managed_info.get('managed_engines', []):
        print(f"    - {eng['engine_id']}: {eng['pw_path']}")
    
    print("\n" + "=" * 80)
    
    # Assertions for two-state model
    # Mode must be either "external" or "internal"
    assert report.mode in ("external", "internal"), f"Invalid mode: {report.mode}"
    
    # If mode is external, settings.qe.bin_dir must be set
    if report.mode == "external":
        assert report.settings_bin_dir is not None, "External mode requires settings.qe.bin_dir to be set"
        # If resolution succeeded, bin_dir should be valid
        if report.qe_bin_dir:
            assert settings_info.get('is_valid'), f"External bin_dir is invalid: {report.settings_bin_dir}"
        # If resolution failed, there should be an error
        else:
            assert report.error is not None, "External mode failed but no error reported"
    
    # If mode is internal, settings.qe.bin_dir must be null
    if report.mode == "internal":
        assert report.settings_bin_dir is None, "Internal mode requires settings.qe.bin_dir to be null"
        # If resolution succeeded, internal QE should be found
        if report.qe_bin_dir:
            assert report.resolution_reason == "internal_auto_selected", \
                f"Internal QE found but wrong reason: {report.resolution_reason}"
        # If resolution failed, there should be an error
        else:
            assert report.error is not None, "Internal mode failed but no error reported"
    
    # No legacy fallback should occur
    assert not report.resolution_reason.startswith("legacy_"), \
        f"Legacy resolution detected: {report.resolution_reason}. Two-state model should not use legacy paths."
    
    assert report.resolution_reason != "path_fallback", \
        "PATH fallback is not supported in two-state model."


def test_qe_resolution_two_state_model():
    """
    Assert that QE resolution follows the two-state model:
    1. External QE: settings.qe.bin_dir is set (must validate pw* exists)
    2. Internal QE: settings.qe.bin_dir is null (auto-select from .qmatsuite/engines/qe/**/bin)
    
    This test verifies:
    a) Mode is correctly reported as "external" or "internal"
    b) External mode validates bin_dir and raises error if invalid (no fallback)
    c) Internal mode finds QE from .qmatsuite/engines/qe/**/bin or raises error
    d) No PATH/QE_HOME/shell/disk fallbacks are used
    """
    from quantumvitas.core.settings import load_settings
    
    settings = load_settings()
    report = diagnose_qe_resolution()
    
    # Verify mode matches settings
    if settings.qe.bin_dir:
        assert report.mode == "external", \
            f"settings.qe.bin_dir is set but mode is {report.mode}, expected 'external'"
        
        # If external bin_dir is invalid, should have error
        if report.error:
            assert report.resolution_reason == "external_invalid", \
                f"External bin_dir invalid but wrong reason: {report.resolution_reason}"
            assert "invalid" in report.error.lower() or "missing pw" in report.error.lower(), \
                f"Error message should mention invalid/missing pw: {report.error}"
        else:
            # If valid, should have resolved bin_dir
            assert report.qe_bin_dir is not None, \
                "External mode with valid bin_dir should resolve to qe_bin_dir"
            assert report.resolution_reason == "external_explicit", \
                f"External mode should have reason 'external_explicit', got: {report.resolution_reason}"
    else:
        assert report.mode == "internal", \
            f"settings.qe.bin_dir is null but mode is {report.mode}, expected 'internal'"
        
        # If internal QE not found, should have error
        if report.error:
            assert report.resolution_reason == "internal_not_found", \
                f"Internal QE not found but wrong reason: {report.resolution_reason}"
            assert "internal QE" in report.error.lower() or ".qmatsuite" in report.error.lower(), \
                f"Error message should mention internal QE: {report.error}"
        else:
            # If found, should have resolved bin_dir
            assert report.qe_bin_dir is not None, \
                "Internal mode with QE found should resolve to qe_bin_dir"
            assert report.resolution_reason == "internal_auto_selected", \
                f"Internal mode should have reason 'internal_auto_selected', got: {report.resolution_reason}"
            # Should report internal candidates
            assert "internal_candidates" in report.inputs_used or "selected_bin_dir" in report.inputs_used, \
                "Internal mode should report candidates or selected bin_dir"
    
    # Verify no legacy fallbacks
    assert not report.resolution_reason.startswith("legacy_"), \
        f"Legacy resolution detected: {report.resolution_reason}. Two-state model should not use legacy paths."
    
    assert report.resolution_reason != "path_fallback", \
        "PATH fallback is not supported in two-state model."

