"""
Quick integration tests for PH module.

These tests are selected from the QE official test-suite as representative
tests for CI. They test the ph.x workflow (pw.x -> ph.x -> q2r.x -> matdyn.x).

These tests require QE installation and will be skipped gracefully if not available.
"""

import pytest
import sys
from pathlib import Path
import tempfile
import shutil
import os
import subprocess

# Add src to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "extended-tests"))
sys.path.insert(0, str(project_root))

from quantumvitas.core.engines.qe import QuantumEspressoEngine
from quantumvitas.core.engines.base import EngineConfig
from quantumvitas.core.engines.qe_input import QEInputParser, QEInputGenerator

# Import shared test utilities
from tests.core.qe_test_utils import parse_jobconfig

# Import from extended-tests/utils
try:
    from utils.qe_module_base import run_test_category
except ImportError:
    # Fallback if extended-tests not available
    def run_test_category(*args, **kwargs):
        return []

# Mark as quick test
pytestmark = [pytest.mark.quick, pytest.mark.requires_qe]

# PH test categories for CI
PH_CI_TESTS = [
    {
        "category": "ph_1d",
        "description": "1D phonon calculation"
    },
    {
        "category": "ph_2d",
        "description": "2D phonon calculation"
    }
]


@pytest.fixture(scope="module")
def qe_engine():
    """Get QE engine (auto-detects installation)."""
    # Create engine without explicit path - it will auto-detect
    config = EngineConfig(name="qe")
    engine = QuantumEspressoEngine(config)
    
    # Check if installation is valid
    if not engine.installation.is_valid():
        pytest.skip("QE installation not found. "
                   f"Reason: QE_BIN_DIR environment variable not set, default location not found, "
                   f"and pw.x not found in system PATH. "
                   f"Please set QE_BIN_DIR or install QE at the default location.")
    
    # Check if required executables exist
    required_exes = ["pw.x", "ph.x"]
    missing_exes = []
    for exe in required_exes:
        if not engine.get_executable_path(exe):
            missing_exes.append(exe)
    
    if missing_exes:
        pytest.skip(f"Required QE executables not found. "
                   f"Reason: Missing executables: {', '.join(missing_exes)}. "
                   f"These are required for PH workflow tests.")
    
    return engine


@pytest.fixture(scope="module")
def test_suite_dir(qe_engine):
    """Get test suite directory (prefer local copy, fallback to test-suite)."""
    # First, try local copy in tests directory
    local_test_data = Path(__file__).parent / "ci_test_data"
    if local_test_data.exists() and (local_test_data / "ph_1d").exists():
        return local_test_data
    
    # Use engine's auto-detected test-suite directory
    test_suite = qe_engine.test_suite_dir
    if not test_suite or not test_suite.exists():
        pytest.skip("QE test-suite not found and local test data not available. "
                   f"Reason: Test suite directory not found and "
                   f"local test data in ci_test_data/ is not available. "
                   f"Either install QE with test-suite or ensure ci_test_data/ contains test files.")
    
    return test_suite


class TestPHQuickTests:
    """Quick PH tests selected from official test-suite."""
    
    @pytest.mark.parametrize("test_info", PH_CI_TESTS)
    def test_ph_quick(self, test_info, qe_engine, test_suite_dir, tmp_path):
        """
        Run a quick PH test from the official test-suite.
        
        This test runs the full ph.x workflow (pw.x -> ph.x -> q2r.x -> matdyn.x),
        verifying that each step completes successfully.
        """
        category = test_info["category"]
        
        # Get test category directory
        category_dir = test_suite_dir / category
        if not category_dir.exists():
            pytest.skip(f"Test category directory not found: {category_dir}. "
                       f"Reason: Category '{category}' does not exist in test suite.")
        
        # Parse jobconfig to get test files
        # Try multiple locations for jobconfig
        jobconfig_paths = [
            test_suite_dir / "jobconfig",
        ]
        
        # Also try from engine's test_suite_dir if different
        if qe_engine.test_suite_dir and qe_engine.test_suite_dir != test_suite_dir:
            jobconfig_paths.insert(0, qe_engine.test_suite_dir / "jobconfig")
        
        jobconfig_path = None
        for path in jobconfig_paths:
            if path and path.exists():
                jobconfig_path = Path(path).resolve()
                break
        
        if not jobconfig_path:
            pytest.skip(f"jobconfig file not found. "
                       f"Reason: Cannot locate QE test-suite jobconfig file. "
                       f"This file is required to determine test order and files.")
        
        all_tests = parse_jobconfig(jobconfig_path, "ph_")
        
        if category not in all_tests:
            pytest.skip(f"Category '{category}' not found in jobconfig. "
                       f"Reason: The category '{category}' is not defined in the jobconfig file. "
                       f"Available categories: {list(all_tests.keys())}")
        
        test_files = all_tests[category]
        if not test_files:
            pytest.skip(f"No test files found for category '{category}'. "
                       f"Reason: Category '{category}' exists in jobconfig but has no test files defined.")
        
        # Executable map for ph workflow
        executable_map = {
            "1": "pw.x",
            "2": "ph.x",
            "3": "q2r.x",
            "4": "matdyn.x",
            "5": "lambda.x",
            "6": "dvscf_q2r.x",
            "7": "postahc.x",
            "8": "matdyn.x",
            "9": "dynmat.x",
            "11": "ph.x",
            "12": "pw.x",
            "13": "ph.x",
            "default": "ph.x"
        }
        
        # Create working directory
        working_dir = tmp_path / f"test_{category}"
        working_dir.mkdir()
        
        # Determine test suite directory
        actual_test_suite = test_suite_dir
        if (test_suite_dir.parent / "test-suite").exists():
            actual_test_suite = test_suite_dir.parent / "test-suite"
        elif Path(test_suite_dir).name != "test-suite":
            # Try to find test-suite
            possible_paths = [
                Path.home() / "src" / "q-e-qe-7.5" / "test-suite",
                test_suite_dir.parent / "test-suite"
            ]
            for path in possible_paths:
                if Path(path).exists():
                    actual_test_suite = Path(path)
                    break
        
        # Run test category
        results = run_test_category(
            category,
            test_files,
            actual_test_suite,
            qe_engine,
            executable_map,
            timeout=300,  # 5 minute timeout for ph tests
            max_tests=None
        )
        
        # Check results
        passed = sum(1 for r in results if r.get("success", False))
        failed = len(results) - passed
        
        # Print summary
        if failed > 0:
            failed_tests = [r for r in results if not r.get("success", False)]
            error_messages = []
            for r in failed_tests:
                error = r.get("error") or r.get("message") or "Unknown error"
                error_messages.append(f"{r.get('file', 'unknown')}: {str(error)[:100]}")
            
            pytest.fail(
                f"PH test category '{category}' failed: {failed}/{len(results)} tests failed.\n"
                f"Failed tests:\n" + "\n".join(error_messages)
            )
        
        # All tests passed
        assert passed == len(results), f"Expected all {len(results)} tests to pass, but {failed} failed"


# Fallback: Simple test that doesn't require QE installation
@pytest.mark.quick
def test_ph_basic_parsing():
    """Basic test that doesn't require QE installation."""
    content = """&inputph
    tr2_ph = 1.0d-12
    prefix = 'test'
    outdir = './'
/
"""
    qe_input = QEInputParser.parse_string(content)
    assert qe_input.get_namelist("inputph") is not None
    
    generated = QEInputGenerator.generate(qe_input)
    assert "&inputph" in generated
    assert "tr2_ph" in generated

