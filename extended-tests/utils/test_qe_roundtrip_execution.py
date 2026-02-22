#!/usr/bin/env python3
"""
Legacy test utilities - DEPRECATED.

This file is kept for backward compatibility but most functions have been moved:
- Pseudopotential resolution → use ensure_qe_pseudos from qmatsuite.core.pseudo
- download_pseudopotential → src/qmatsuite/core/engines/qe_pseudopotentials.py
- set_outdir_to_temp, set_pseudo_dir_to_temp → tests/core/qe_step_runner.py
- run_command_with_timeout, TimeoutError → tests/core/qe_test_utils.py
- verify_qe_output → tests/core/qe_step_verification.py (verify_step_result)
- run_input_roundtrip_execution → REMOVED (use run_and_verify_step_with_assert from tests.core)

All new code should import from the new locations.
"""

from qmatsuite.core.engines.qe_pseudopotentials import download_pseudopotential
from qmatsuite.calculation.input_runner import set_outdir_to_temp, set_pseudo_dir_to_temp
from tests.core import run_command_with_timeout, TimeoutError

# Re-export for backward compatibility
__all__ = [
    "download_pseudopotential",
    "set_outdir_to_temp",
    "set_pseudo_dir_to_temp",
    "run_command_with_timeout",
    "TimeoutError",
]
