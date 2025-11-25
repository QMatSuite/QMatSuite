"""
Quick integration tests for PH module.

These tests are selected from the QE official test-suite as representative
tests for CI. They test the ph.x workflow (pw.x -> ph.x -> q2r.x -> matdyn.x).

These tests require QE installation and will fail if QE is not available.
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
from quantumvitas.core.engines.qe_input import QEInputParser, QEInputGenerator, QEInput

# Import shared test utilities
from tests.core.qe_test_utils import parse_jobconfig
from tests.core.qe_step_runner import run_and_verify_step_with_assert

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
    
    # Check if installation is valid - fail if not found (don't skip)
    if not engine.installation.is_valid():
        raise RuntimeError(
            "QE installation not found. "
            f"Reason: QE_BIN_DIR environment variable not set, default location not found, "
            f"and pw.x not found in system PATH. "
            f"Please set QE_BIN_DIR or install QE at the default location."
        )
    
    # Check if required executables exist - fail if not found (don't skip)
    required_exes = ["pw.x", "ph.x"]
    missing_exes = []
    for exe in required_exes:
        if not engine.detect_executable(exe):
            missing_exes.append(exe)
    
    if missing_exes:
        raise RuntimeError(
            f"Required QE executables not found. "
            f"Reason: Missing executables: {', '.join(missing_exes)}. "
            f"These are required for PH workflow tests."
        )
    
    return engine


@pytest.fixture(scope="module")
def test_data_dir():
    """Get local test data directory (no dependency on QE test-suite)."""
    local_test_data = Path(__file__).parent / "ci_test_data"
    if not local_test_data.exists():
        raise RuntimeError(
            f"Local test data directory not found: {local_test_data}. "
            f"Reason: ci_test_data/ directory is required for PH tests."
        )
    
    if not (local_test_data / "ph_1d").exists():
        raise RuntimeError(
            f"PH test data not found: {local_test_data / 'ph_1d'}. "
            f"Reason: ph_1d directory is required in ci_test_data/."
        )
    
    return local_test_data


class TestPHQuickTests:
    """Quick PH tests selected from official test-suite."""
    
    @pytest.mark.parametrize("test_info", PH_CI_TESTS)
    def test_ph_quick(self, test_info, qe_engine, test_data_dir, tmp_path):
        """
        Run a quick PH test using local test data (no dependency on QE test-suite).
        
        This test runs the full ph.x workflow (pw.x -> ph.x -> q2r.x -> matdyn.x),
        verifying that each step completes successfully.
        """
        category = test_info["category"]
        
        # Get test category directory from local test data
        category_dir = test_data_dir / category
        if not category_dir.exists():
            raise RuntimeError(
                f"Test category directory not found: {category_dir}. "
                f"Reason: Category '{category}' does not exist in local test data."
            )
        
        # Parse jobconfig from local test data (no dependency on QE test-suite)
        jobconfig_path = test_data_dir / "jobconfig"
        if not jobconfig_path.exists():
            raise RuntimeError(
                f"jobconfig file not found: {jobconfig_path}. "
                f"Reason: jobconfig file is required in ci_test_data/ to determine test order and files."
            )
        
        all_tests = parse_jobconfig(jobconfig_path, "ph_")
        
        if category not in all_tests:
            raise RuntimeError(
                f"Category '{category}' not found in jobconfig. "
                f"Reason: The category '{category}' is not defined in the jobconfig file. "
                f"Available categories: {list(all_tests.keys())}"
            )
        
        test_files = all_tests[category]
        if not test_files:
            raise RuntimeError(
                f"No test files found for category '{category}'. "
                f"Reason: Category '{category}' exists in jobconfig but has no test files defined."
            )
        
        # Executable map for ph workflow (maps jobconfig args to executable names)
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
        
        # Create working directory for workflow (all steps share the same directory)
        working_dir = tmp_path / f"test_{category}"
        working_dir.mkdir()
        
        # Run each step sequentially and verify immediately (step1 -> test step1 -> step2 -> test step2)
        failed_steps = []
        for i, (input_file, args) in enumerate(test_files):
            input_path = category_dir / input_file
            if not input_path.exists():
                pytest.fail(f"Input file not found: {input_path}")
            
            # Determine executable from args
            executable_name = executable_map.get(args, executable_map.get("default", "pw.x"))
            
            # Check for reference output file
            reference_file = None
            # Try to find reference file (if exists)
            ref_dir = category_dir / "reference_out"
            if ref_dir.exists():
                ref_name = input_path.stem + ".out"
                ref_path = ref_dir / ref_name
                if ref_path.exists():
                    reference_file = ref_path
            
            # Run and verify step using centralized function
            try:
                run_and_verify_step_with_assert(
                    input_file=input_path,
                    qe_engine=qe_engine,
                    working_dir=working_dir,
                    reference_file=reference_file,
                    category=category,
                    timeout=300,  # 5 minute timeout for ph tests
                    step_type=None,  # Auto-detect from input
                )
            except AssertionError as e:
                failed_steps.append(f"{input_file} (step {i+1}/{len(test_files)}): {str(e)}")
                # For workflow tests, stop on first failure
                break
        
        # Report failures
        if failed_steps:
            pytest.fail(
                f"PH test category '{category}' failed: {len(failed_steps)}/{len(test_files)} steps failed.\n"
                f"Failed steps:\n" + "\n".join(failed_steps)
            )


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

