"""
Test QE resolution diagnostics.

This test verifies that QE resolution follows the intended priority
and identifies when legacy auto-detection bypasses the registry.
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
    Diagnostic test: print QE resolution report.
    
    This test does NOT fail - it's informational to help understand
    how QE is being resolved in the current environment.
    """
    # Get full diagnostic report
    report = diagnose_qe_resolution(check_legacy=True)
    settings_info = check_settings_for_external_engines()
    env_info = check_environment_variables()
    managed_info = check_managed_engines()
    
    print("\n" + "=" * 80)
    print("QE RESOLUTION DIAGNOSTICS")
    print("=" * 80)
    print(f"\nResolution Reason: {report.resolution_reason}")
    print(f"Resolved Engine ID: {report.resolved_engine_id}")
    print(f"Resolved pw.x Path: {report.resolved_pw_path}")
    
    print("\n--- Inputs Used ---")
    for key, value in report.inputs_used.items():
        print(f"  {key}: {value}")
    
    if report.warnings:
        print("\n--- Warnings ---")
        for warning in report.warnings:
            print(f"  ⚠️  {warning}")
    
    print("\n--- Settings.json ---")
    print(f"  Discovered Engine ID: {settings_info.get('discovered_engine_id')}")
    print(f"  Default Engine ID: {settings_info.get('default_engine_id')}")
    print(f"  Allow PATH Fallback: {settings_info.get('allow_path_fallback')}")
    print(f"  External Engines: {settings_info.get('external_engines_count')}")
    
    print("\n--- Environment Variables ---")
    for key, value in env_info.items():
        if value:
            print(f"  {key}: {value}")
    
    print("\n--- Managed Engines ---")
    print(f"  Engines Dir Exists: {managed_info.get('engines_dir_exists')}")
    print(f"  Engines Dir Path: {managed_info.get('engines_dir_path')}")
    print(f"  Managed Engines Count: {managed_info.get('managed_engines_count')}")
    for eng in managed_info.get('managed_engines', []):
        print(f"    - {eng['engine_id']}: {eng['pw_path']}")
    
    print("\n" + "=" * 80)
    
    # Assertions for expected behavior
    # In local dev without managed engine, we should either:
    # 1. Have a managed engine, OR
    # 2. Have an explicit external engine registered, OR
    # 3. Fail with clear error (not silently use PATH)
    
    if report.resolution_reason == "path_fallback":
        pytest.fail(
            f"QE resolved via PATH fallback, but this should not happen by default.\n"
            f"Resolution report: {report.to_dict()}\n"
            f"Either install a managed engine or explicitly enable allow_path_fallback in test setup."
        )
    
    if report.resolution_reason.startswith("legacy_"):
        pytest.fail(
            f"QE resolved via legacy auto-detection, bypassing registry system.\n"
            f"Resolution reason: {report.resolution_reason}\n"
            f"Inputs used: {report.inputs_used}\n"
            f"This violates 'default managed-only' policy. Tests should use registry or explicitly configure engines."
        )
    
    if report.resolution_reason == "no_engine_found":
        # This is OK if we're testing the failure case
        # But in normal tests, we should have an engine
        print("\n⚠️  No QE engine found. This may be expected for some tests.")


def test_qe_resolution_requires_managed_or_explicit():
    """
    Assert that QE resolution requires either:
    1. A managed engine installed, OR
    2. An explicit external engine registered in settings
    
    This test should fail if QE is resolved via PATH or legacy auto-detection
    without explicit configuration.
    """
    from quantumvitas.core.settings import load_settings
    
    settings = load_settings()
    report = diagnose_qe_resolution(check_legacy=False)  # Don't check legacy paths
    
    # If PATH fallback is enabled, that's OK (explicit opt-in)
    if settings.qe.allow_path_fallback:
        # PATH fallback is explicitly enabled, so it's OK
        return
    
    # Check if we have a valid resolution through registry
    valid_reasons = {
        "project_override",
        "settings_discovered_engine_id",
        "settings_defaults_qe_engine_id",
        "managed_engine_fallback",
    }
    
    if report.resolution_reason not in valid_reasons:
        pytest.fail(
            f"QE resolution did not use registry system.\n"
            f"Resolution reason: {report.resolution_reason}\n"
            f"Expected one of: {valid_reasons}\n"
            f"Full report: {report.to_dict()}\n"
            f"\nTo fix:\n"
            f"1. Install a managed QE engine to .qmatsuite/engines/qe/\n"
            f"2. Or register an external engine in settings.json\n"
            f"3. Or explicitly enable allow_path_fallback in test setup"
        )

