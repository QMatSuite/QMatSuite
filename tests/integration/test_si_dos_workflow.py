"""
Test SCF -> NSCF -> DOS workflow using 4_Si_DOS tutorial example.

This test validates the complete workflow:
1. SCF calculation
2. NSCF calculation (reads from SCF .save)
3. DOS calculation (reads from NSCF .save)
"""

import pytest
from pathlib import Path
import time

from quantumvitas.core.engines.qe import QuantumEspressoEngine
from quantumvitas.io import QEInputParser, QEInputGenerator
from quantumvitas.core.engines.base import EngineConfig
from tests.core.qe_step_runner import (
    run_and_verify_step_with_assert,
    get_default_working_dir,
)
from quantumvitas.workflow.input_runner import set_outdir_to_temp
from tests.core.qe_test_utils import parse_jobconfig


@pytest.fixture
def test_data_dir():
    """Fixture for CI test data directory."""
    project_root = Path(__file__).parent.parent.parent
    ci_test_data_dir = project_root / "tests" / "integration" / "ci_test_data"
    if not ci_test_data_dir.exists():
        pytest.skip(f"CI test data not found: {ci_test_data_dir}")
    return ci_test_data_dir


@pytest.fixture
def si_dos_dir(test_data_dir):
    """Fixture for 4_Si_DOS test data directory."""
    return test_data_dir / "4_Si_DOS"


@pytest.fixture
def qe_engine():
    """Fixture for QuantumEspressoEngine."""
    config = EngineConfig(name="qe")
    engine = QuantumEspressoEngine(config)
    if not engine.find_executable("pw.x"):
        raise RuntimeError("QE installation not found. pw.x executable is required.")
    return engine


class TestSiDOSWorkflow:
    """Test suite for SCF -> NSCF -> DOS workflow."""
    
    def test_parse_scf_input(self, si_dos_dir):
        """Test parsing SCF input file."""
        scf_file = si_dos_dir / "si.1_scf.in"
        qe_input = QEInputParser.parse_file(scf_file)
        
        control = qe_input.get_namelist('control')
        assert control.get('calculation') == 'scf'
        assert control.get('prefix') == 'si'
        
        system = qe_input.get_namelist('system')
        assert system.get('ecutwfc') > 0
    
    def test_parse_nscf_input(self, si_dos_dir):
        """Test parsing NSCF input file."""
        nscf_file = si_dos_dir / "si.2_nscf.in"
        qe_input = QEInputParser.parse_file(nscf_file)
        
        control = qe_input.get_namelist('control')
        assert control.get('calculation') == 'nscf'
        assert control.get('prefix') == 'si'
    
    def test_parse_dos_input(self, si_dos_dir):
        """Test parsing DOS input file."""
        dos_file = si_dos_dir / "si.3_dos.in"
        qe_input = QEInputParser.parse_file(dos_file)
        
        dos_namelist = qe_input.get_namelist('dos')
        assert dos_namelist is not None
        assert dos_namelist.get('fildos') == 'si.dos.dat'
    
    def test_workflow_sequence(self, si_dos_dir, test_data_dir):
        """Test that workflow files are in correct sequence from jobconfig."""
        jobconfig_path = test_data_dir / "jobconfig"
        if not jobconfig_path.exists():
            pytest.skip(f"jobconfig file not found: {jobconfig_path}")
        
        all_tests = parse_jobconfig(jobconfig_path, "")
        category = "4_Si_DOS"
        
        if category not in all_tests:
            pytest.skip(f"Category '{category}' not found in jobconfig")
        
        test_files = all_tests[category]
        
        # Verify all files exist and are in correct sequence
        for input_file, args in test_files:
            file_path = si_dos_dir / input_file
            assert file_path.exists(), f"Workflow file not found: {file_path}"
        
        # Verify calculation types
        scf_input = QEInputParser.parse_file(si_dos_dir / test_files[0][0])
        nscf_input = QEInputParser.parse_file(si_dos_dir / test_files[1][0])
        dos_input = QEInputParser.parse_file(si_dos_dir / test_files[2][0])
        
        assert scf_input.get_namelist('control').get('calculation') == 'scf'
        assert nscf_input.get_namelist('control').get('calculation') == 'nscf'
        assert dos_input.get_namelist('dos') is not None
    
    def test_run_full_workflow(self, si_dos_dir, qe_engine):
        """Test running the complete SCF -> NSCF -> DOS workflow."""
        project_root = Path(__file__).parent.parent.parent
        working_dir = get_default_working_dir(project_root, "4_Si_DOS")
        
        # Step 1: SCF
        scf_file = si_dos_dir / "si.1_scf.in"
        scf_reference = si_dos_dir / "reference_out" / "si.1_scf.out"
        scf_result = run_and_verify_step_with_assert(
            input_file=scf_file,
            qe_engine=qe_engine,
            working_dir=working_dir,
            reference_file=scf_reference,
            category="4_Si_DOS",
            timeout=300,
        )
        assert scf_result.success
        
        time.sleep(0.5)
        
        # Step 2: NSCF
        nscf_file = si_dos_dir / "si.2_nscf.in"
        nscf_reference = si_dos_dir / "reference_out" / "si.2_nscf.out"
        nscf_result = run_and_verify_step_with_assert(
            input_file=nscf_file,
            qe_engine=qe_engine,
            working_dir=working_dir,
            reference_file=nscf_reference,
            category="4_Si_DOS",
            timeout=300,
        )
        assert nscf_result.success
        
        time.sleep(0.5)
        
        # Step 3: DOS
        dos_file = si_dos_dir / "si.3_dos.in"
        dos_input = QEInputParser.parse_file(dos_file)
        set_outdir_to_temp(dos_input, project_root)
        
        # Write input to working_dir
        dos_input_file = working_dir / "si.3_dos.in"
        QEInputGenerator.write_file(dos_input, dos_input_file)
        
        # Run dos.x
        dos_executable = qe_engine.get_executable_path("dos.x")
        if not dos_executable:
            pytest.skip("dos.x not found")
        
        import subprocess
        import os
        env = os.environ.copy()
        env['OMP_NUM_THREADS'] = '1'
        
        with open(dos_input_file, 'r') as stdin_file:
            result = subprocess.run(
                [dos_executable],
                cwd=str(working_dir),
                stdin=stdin_file,
                capture_output=True,
                text=True,
                timeout=300,
                env=env
            )
        
        # Write output to working_dir
        output_file = working_dir / "si.3_dos.out"
        output_file.write_text(result.stdout)
        
        assert result.returncode == 0, f"dos.x failed: {result.stderr}"
        assert "JOB DONE" in result.stdout
