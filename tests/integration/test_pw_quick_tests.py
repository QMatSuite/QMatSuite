"""
Quick integration tests for PW module.

These tests are selected from the QE official test-suite as the shortest,
most representative tests for CI. They are fast and cover key functionality.

These tests require QE installation and will be skipped gracefully if not available.
"""

import pytest
import sys
from pathlib import Path
import tempfile
import shutil
import os

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from quantumvitas.core.engines.qe import QuantumEspressoEngine
from quantumvitas.core.engines.base import EngineConfig
from quantumvitas.core.engines.qe_input import QEInputParser, QEInputGenerator

# Mark as quick test
pytestmark = [pytest.mark.quick, pytest.mark.requires_qe]

# These tests will be populated from the statistics collection
QUICK_PW_TESTS = []


def load_quick_tests():
    """Load the selected quick tests from statistics."""
    stats_file = Path(__file__).parent.parent.parent / "extended-tests" / "pw_test_stats.json"
    if stats_file.exists():
        import json
        try:
            with open(stats_file) as f:
                data = json.load(f)
                tests = data.get("selected_ci_tests", [])
                # Add success flag if not present (for backward compatibility)
                for test in tests:
                    if "success" not in test:
                        test["success"] = True
                return tests
        except Exception as e:
            pytest.skip(f"Could not load quick tests: {e}")
    return []


@pytest.fixture(scope="module")
def qe_engine():
    """Create QE engine instance."""
    # Try to find QE from environment or default location
    qe_bin = os.environ.get("QE_BIN_DIR")
    if qe_bin:
        qe_bin = Path(qe_bin)
    else:
        # In CI, QE might not be available - skip gracefully
        qe_bin = Path.home() / "src" / "q-e-qe-7.5" / "bin"
    
    if not qe_bin.exists():
        pytest.skip("QE installation not found (QE_BIN_DIR not set and default location not found)")
    
    # Check if pw.x exists
    pw_x = qe_bin / "pw.x"
    if not pw_x.exists():
        pytest.skip(f"pw.x not found in {qe_bin}")
    
    config = EngineConfig(name="qe", executable_path=qe_bin)
    engine = QuantumEspressoEngine(config)
    
    # Verify engine can find executable
    if not engine.get_executable_path("pw.x"):
        pytest.skip("Cannot find pw.x executable")
    
    return engine


@pytest.fixture(scope="module")
def test_suite_dir():
    """Get test suite directory (prefer local copy, fallback to test-suite)."""
    # First, try local copy in tests directory
    local_test_data = Path(__file__).parent / "ci_test_data"
    if local_test_data.exists() and (local_test_data / "manifest.json").exists():
        return local_test_data
    
    # Fallback to QE test-suite directory
    qe_bin = os.environ.get("QE_BIN_DIR")
    if qe_bin:
        qe_bin = Path(qe_bin)
    else:
        qe_bin = Path.home() / "src" / "q-e-qe-7.5" / "bin"
    
    if not qe_bin.exists():
        pytest.skip("QE installation not found and local test data not available")
    
    if qe_bin.is_dir():
        qe_root = qe_bin.parent
    else:
        qe_root = qe_bin.parent.parent
    
    test_suite = qe_root / "test-suite"
    if not test_suite.exists():
        pytest.skip("QE test-suite not found and local test data not available")
    
    return test_suite


class TestPWQuickTests:
    """Quick PW tests selected from official test-suite."""
    
    @pytest.fixture(autouse=True)
    def setup_tests(self):
        """Load quick tests."""
        global QUICK_PW_TESTS
        if not QUICK_PW_TESTS:
            QUICK_PW_TESTS = load_quick_tests()
    
    @pytest.fixture(autouse=True, scope="class")
    def setup_tests(self):
        """Load quick tests once per test class."""
        global QUICK_PW_TESTS
        if not QUICK_PW_TESTS:
            QUICK_PW_TESTS = load_quick_tests()
    
    @pytest.mark.parametrize("test_info", QUICK_PW_TESTS if QUICK_PW_TESTS else [])
    def test_pw_quick(self, test_info, qe_engine, test_suite_dir, tmp_path):
        """
        Run a quick PW test from the official test-suite.
        
        This test parses, generates, and runs a QE input file,
        verifying that it completes successfully.
        """
        if not QUICK_PW_TESTS:
            pytest.skip("Quick tests not loaded. Run extended-tests/scripts/run_pw_all_with_stats.py first")
        
        # Skip if test was marked as failed in stats
        if not test_info.get("success", True):
            pytest.skip(f"Test {test_info['test_file']} was marked as failed in statistics")
        
        category = test_info["category"]
        test_file = test_info["test_file"]
        
        # Get test file path
        test_path = test_suite_dir / category / test_file
        if not test_path.exists():
            pytest.skip(f"Test file not found: {test_path}")
        
        # Create working directory
        working_dir = tmp_path / f"test_{category}_{test_file}"
        working_dir.mkdir()
        
        # Copy input file
        working_input = working_dir / test_file
        shutil.copy2(test_path, working_input)
        
        # Parse input
        qe_input = QEInputParser.parse_file(test_path)
        
        # Generate new input
        generated_input = working_dir / "generated.in"
        QEInputGenerator.write_file(qe_input, generated_input)
        
        # Ensure pseudopotentials (simplified - would need full implementation)
        env = os.environ.copy()
        env['ESPRESSO_PSEUDO'] = str(working_dir)
        
        # Run pw.x
        exe_path = qe_engine.get_executable_path("pw.x")
        if not exe_path or not exe_path.exists():
            pytest.skip("pw.x not found")
        
        import subprocess
        stdout_file = working_dir / "stdout.txt"
        stderr_file = working_dir / "stderr.txt"
        
        try:
            with open(stdout_file, 'w') as fout, open(stderr_file, 'w') as ferr:
                proc = subprocess.run(
                    [str(exe_path), "-inp", str(generated_input)],
                    cwd=working_dir,
                    stdout=fout,
                    stderr=ferr,
                    timeout=120,  # 2 minute timeout for quick tests
                    env=env
                )
        except subprocess.TimeoutExpired:
            pytest.fail(f"Test {test_file} timed out after 120 seconds")
        
        # Verify
        assert proc.returncode == 0, f"pw.x returned {proc.returncode}. Check {stderr_file} for details."
        
        stdout_content = stdout_file.read_text()
        assert "JOB DONE" in stdout_content, f"JOB DONE not found in output. Output: {stdout_content[:500]}"


# Fallback: Simple test that doesn't require QE installation
# This test always runs, even without QE
@pytest.mark.quick
def test_pw_basic_parsing():
    """Basic test that doesn't require QE installation."""
    content = """&control
    calculation = 'scf'
    prefix = 'test'
/
&system
    ibrav = 0
    nat = 2
    ntyp = 1
    ecutwfc = 30.0
/
ATOMIC_SPECIES
Si 28.085 Si.pbe-n-rrkjus.UPF
ATOMIC_POSITIONS alat
Si 0.0 0.0 0.0
Si 0.25 0.25 0.25
K_POINTS gamma
"""
    qe_input = QEInputParser.parse_string(content)
    assert qe_input.get_namelist("control") is not None
    assert qe_input.get_namelist("system") is not None
    
    generated = QEInputGenerator.generate(qe_input)
    assert "&control" in generated
    assert "calculation = 'scf'" in generated

