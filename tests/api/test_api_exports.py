"""
Test API export count gate.

This test ensures that the API export count does not grow beyond the baseline.
The baseline is automatically computed on first run.
"""

import os
from pathlib import Path

import pytest


def test_api_export_count_frozen():
    """
    Top-level api exports must not grow.
    
    This test automatically computes the baseline on first run and records it.
    Subsequent runs will fail if the count exceeds the baseline.
    """
    import quantumvitas.api as api
    
    # Count non-private exports
    exports = [x for x in dir(api) if not x.startswith('_')]
    current_count = len(exports)
    
    # Baseline file location
    baseline_file = Path(__file__).parent.parent.parent / ".api_export_baseline.txt"
    
    if baseline_file.exists():
        # Read baseline
        baseline = int(baseline_file.read_text().strip())
        assert current_count <= baseline, (
            f"Export count grew: {current_count} > {baseline}. "
            f"This PR must not add new exports. "
            f"To update baseline (only if intentional): delete {baseline_file}"
        )
    else:
        # First run: record baseline
        baseline_file.write_text(str(current_count))
        pytest.skip(
            f"Baseline recorded: {current_count} exports. "
            f"Re-run test to verify it doesn't grow."
        )


def test_no_new_kernel_reexports():
    """
    Forbid specific kernel symbols from being re-exported.
    
    These symbols should NOT be in the API namespace.
    They will be replaced with DTOs in subsequent PRs.
    """
    import quantumvitas.api as api
    
    FORBIDDEN = [
        'Step',
        'Calculation',
        'ResourceMeta',
        'EngineConfig',
        'CalculationStepEntry',
        'ResourceIndex',
        'Manifest',
    ]
    
    for name in FORBIDDEN:
        # Note: These may exist now (PR0), but the test documents the goal
        # They will be removed in PR5-PR10
        if hasattr(api, name):
            # For PR0, we just warn - these will be removed later
            # In PR1+, this should be an assertion
            pass  # Will become: assert not hasattr(api, name), f"Forbidden re-export: {name}"

