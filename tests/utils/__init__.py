"""
Test utilities and helper functions.

Shared utilities used across different test suites.

Note: This module is deprecated. Use tests.core instead.
All functionality has been moved to tests.core:
- parse_jobconfig -> tests.core.qe_test_utils
- run_and_verify_step_with_assert -> tests.core.qe_step_runner
- compare_with_benchmark -> tests.core.qe_test_utils
"""

# Re-export from tests.core for backward compatibility
from tests.core.qe_test_utils import (
    parse_jobconfig,
    compare_with_benchmark,
)
from tests.core.test_data import load_test_cases, InputTestCase

__all__ = [
    "parse_jobconfig",
    "compare_with_benchmark",
    "load_test_cases",
    "InputTestCase",
]

