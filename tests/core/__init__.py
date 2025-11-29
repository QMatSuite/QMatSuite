"""
Test framework core components.

Provides base classes and utilities for different types of tests.
"""

from .base import TestSuite, TestCase, TestResult
from .runner import TestRunner
from .qe_test_utils import (
    parse_jobconfig,
    extract_ph_frequencies,
    compare_with_benchmark,
    run_test_category_workflow,  # Replacement for qe_module_base.run_test_category
    run_command_with_timeout,
    TimeoutError,
)
from .thresholds import (
    get_energy_tolerance,
    get_frequency_threshold,
    get_fermi_energy_tolerance,
    DEFAULT_ENERGY_TOLERANCE,
    DEFAULT_FREQUENCY_THRESHOLD,
    FERMI_ENERGY_TOLERANCE,
)
from .qe_step_verification import (
    verify_step_result,
    verify_step_with_reference,
)
from .qe_step_runner import (
    run_and_verify_step,
    run_and_verify_step_with_assert,
)
from .test_data import load_test_cases, InputTestCase

__all__ = [
    "TestSuite",
    "TestCase",
    "TestResult",
    "TestRunner",
    "parse_jobconfig",
    "extract_ph_frequencies",
    "compare_with_benchmark",
    "run_test_category_workflow",  # Replacement for qe_module_base.run_test_category
    "run_command_with_timeout",
    "TimeoutError",
    "get_energy_tolerance",
    "get_frequency_threshold",
    "get_fermi_energy_tolerance",
    "DEFAULT_ENERGY_TOLERANCE",
    "DEFAULT_FREQUENCY_THRESHOLD",
    "FERMI_ENERGY_TOLERANCE",
    "verify_step_result",
    "verify_step_with_reference",
    "run_and_verify_step",
    "run_and_verify_step_with_assert",
    "load_test_cases",
    "InputTestCase",
]

