"""
Test SCF -> NSCF -> Bands -> bands.x workflow using 7_Si_bandStructure tutorial example.

This test validates the complete workflow:
1. SCF calculation
2. NSCF calculation (reads from SCF .save)
3. Bands calculation (reads from NSCF .save)
4. bands.x post-processing
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

pytestmark = pytest.mark.qe_core


@pytest.fixture
def si_bands_dir(ci_test_data_dir):
    """Fixture for 7_Si_bandStructure test data directory."""
    return ci_test_data_dir / "7_Si_bandStructure"


@pytest.fixture
def qe_engine():
    """Fixture for QuantumEspressoEngine."""
    config = EngineConfig(name="qe")
    engine = QuantumEspressoEngine(config)
    if not engine.find_executable("pw.x"):
        raise RuntimeError("QE installation not found. pw.x executable is required.")
    return engine


class TestSiBandsWorkflow:
    """Test suite for SCF -> NSCF -> Bands -> bands.x workflow."""

    def test_run_full_workflow(self, si_bands_dir, qe_engine):
        """Test running the complete SCF -> NSCF -> Bands -> bands.x workflow."""
        project_root = Path(__file__).parent.parent.parent
        working_dir = get_default_working_dir(project_root, "7_Si_bandStructure")
        
        # Step 1: SCF
        scf_file = si_bands_dir / "si.0_scf.in"
        scf_reference = si_bands_dir / "reference_out" / "si.0_scf.out"
        scf_result = run_and_verify_step_with_assert(
            input_file=scf_file,
            qe_engine=qe_engine,
            working_dir=working_dir,
            reference_file=scf_reference,
            category="7_Si_bandStructure",
            timeout=300,
        )
        assert scf_result.success
        
        time.sleep(0.5)
        
        # Step 2: NSCF
        nscf_file = si_bands_dir / "si.1_nscf.in"
        nscf_reference = si_bands_dir / "reference_out" / "si.1_nscf.out"
        nscf_result = run_and_verify_step_with_assert(
            input_file=nscf_file,
            qe_engine=qe_engine,
            working_dir=working_dir,
            reference_file=nscf_reference,
            category="7_Si_bandStructure",
            timeout=300,
        )
        assert nscf_result.success
        
        time.sleep(0.5)
        
        # Step 3: Bands
        bands_file = si_bands_dir / "si.2_bands.in"
        bands_result = run_and_verify_step_with_assert(
            input_file=bands_file,
            qe_engine=qe_engine,
            working_dir=working_dir,
            reference_file=None,
            category="7_Si_bandStructure",
            timeout=300,
        )
        assert bands_result.success
        
        time.sleep(0.5)
        
        # Step 4: bands.x
        bands_pp_file = si_bands_dir / "si.3_bands.pp.in"
        bands_pp_input = QEInputParser.parse_file(bands_pp_file)
        set_outdir_to_temp(bands_pp_input, project_root)
        
        # Write input to working_dir
        bands_pp_input_file = working_dir / "si.3_bands.pp.in"
        QEInputGenerator.write_file(bands_pp_input, bands_pp_input_file)
        
        # Run bands.x
        bands_executable = qe_engine.get_executable_path("bands.x")
        if not bands_executable:
            pytest.skip("bands.x not found")
        
        import subprocess
        import os
        env = os.environ.copy()
        env['OMP_NUM_THREADS'] = '1'
        
        with open(bands_pp_input_file, 'r') as stdin_file:
            result = subprocess.run(
                [bands_executable],
                cwd=str(working_dir),
                stdin=stdin_file,
                capture_output=True,
                text=True,
                timeout=300,
                env=env
            )
        
        # Write output to working_dir
        output_file = working_dir / "si.3_bands.pp.out"
        output_file.write_text(result.stdout)
        
        assert result.returncode == 0, f"bands.x failed: {result.stderr}"
        assert "JOB DONE" in result.stdout
