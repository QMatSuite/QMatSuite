"""
Unit tests for Wannier90 output file handling.

Tests verify:
1. stdout/stderr files don't overwrite between w90_preproc and w90_run
2. Primary output (artifact) is correctly bound to <seed>.wout
3. Pipeline reaches pw2wannier90 step
4. Required artifacts (.nnkp, .wout) are validated
"""

import pytest
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
import shutil

from quantumvitas.core.engines.qe_calculation import QECalculationRunner, StepResult
from quantumvitas.core.engines.qe import QuantumEspressoEngine
from quantumvitas.core.engines.base import EngineConfig


class TestWannier90StdoutStderrNotOverwritten:
    """Test that w90_preproc and w90_run don't overwrite each other's stdout/stderr."""
    
    @pytest.fixture
    def mock_qe_setup(self, tmp_path):
        """Create mock QE installation structure."""
        mock_qe_home = tmp_path / "qe_home"
        mock_bin = mock_qe_home / "bin"
        mock_bin.mkdir(parents=True)
        (mock_bin / "pw.x").touch()
        
        # Mock executables
        for exe_name in ["wannier90.x", "pw2wannier90.x"]:
            mock_exe = mock_bin / exe_name
            script_content = f"""#!/bin/bash
# {exe_name} mock
if [[ "$1" == "-pp" ]]; then
    echo "PREPROC_OUTPUT" >&1
    echo "PREPROC_ERROR" >&2
    touch "$(pwd)/{exe_name.split('.')[0]}.nnkp"
    exit 0
elif [[ "$1" == "diamond" ]]; then
    echo "RUN_OUTPUT" >&1
    echo "RUN_ERROR" >&2
    touch "$(pwd)/diamond.wout"
    exit 0
else
    echo "HELLO" >&1
    echo "ERR" >&2
    exit 0
fi
"""
            mock_exe.write_text(script_content)
            mock_exe.chmod(0o755)
        
        return mock_qe_home
    
    def test_wannier90_stdout_stderr_not_overwritten_between_steps(self, tmp_path, mock_qe_setup):
        """Test that w90_preproc and w90_run write to different stdout/stderr files."""
        config = EngineConfig(
            name="qe",
            qe_home=mock_qe_setup,
        )
        
        with patch.object(QuantumEspressoEngine, 'get_executable_path') as mock_get_exe:
            def get_exe(executable):
                return mock_qe_setup / "bin" / executable
            mock_get_exe.side_effect = get_exe
            
            engine = QuantumEspressoEngine(config)
            runner = QECalculationRunner(engine)
            
            working_dir = tmp_path / "work"
            working_dir.mkdir()
            
            # Step 1: w90_preproc
            input_file_preproc = working_dir / "diamond.win"
            input_file_preproc.write_text("num_wann = 4\n")
            
            result_preproc = runner.run_step(
                input_file=input_file_preproc,
                working_dir=working_dir,
                step_type="w90_preproc",
            )
            
            # Step 2: w90_run
            input_file_run = working_dir / "diamond.win"
            result_run = runner.run_step(
                input_file=input_file_run,
                working_dir=working_dir,
                step_type="w90_run",
            )
            
            # Verify stdout/stderr files exist and are different (using .out/.err naming)
            preproc_stdout = working_dir / "w90_preproc.out"
            preproc_stderr = working_dir / "w90_preproc.err"
            run_stdout = working_dir / "w90_run.out"
            run_stderr = working_dir / "w90_run.err"
            
            assert preproc_stdout.exists(), f"w90_preproc.out should exist: {preproc_stdout}"
            assert preproc_stderr.exists(), f"w90_preproc.err should exist: {preproc_stderr}"
            assert run_stdout.exists(), f"w90_run.out should exist: {run_stdout}"
            assert run_stderr.exists(), f"w90_run.err should exist: {run_stderr}"
            
            # Verify content is different
            preproc_stdout_content = preproc_stdout.read_text()
            run_stdout_content = run_stdout.read_text()
            
            assert "PREPROC_OUTPUT" in preproc_stdout_content
            assert "RUN_OUTPUT" in run_stdout_content
            assert preproc_stdout_content != run_stdout_content, "stdout files should have different content"


class TestW90PreprocPrimaryOutput:
    """Test that w90_preproc primary output is <seed>.wout and .nnkp is required."""
    
    @pytest.fixture
    def mock_qe_setup(self, tmp_path):
        """Create mock QE installation with wannier90.x."""
        mock_qe_home = tmp_path / "qe_home"
        mock_bin = mock_qe_home / "bin"
        mock_bin.mkdir(parents=True)
        (mock_bin / "pw.x").touch()
        
        mock_exe = mock_bin / "wannier90.x"
        script_content = """#!/bin/bash
# Create .nnkp and .wout files
touch "$(pwd)/diamond.nnkp"
touch "$(pwd)/diamond.wout"
echo "Success" >&1
exit 0
"""
        mock_exe.write_text(script_content)
        mock_exe.chmod(0o755)
        return mock_qe_home
    
    def test_w90_preproc_primary_output_is_seed_wout_and_nnkp_required(self, tmp_path, mock_qe_setup):
        """Test that w90_preproc primary output is <seed>.wout and .nnkp existence is required."""
        config = EngineConfig(
            name="qe",
            qe_home=mock_qe_setup,
        )
        
        with patch.object(QuantumEspressoEngine, 'get_executable_path') as mock_get_exe:
            mock_get_exe.return_value = mock_qe_setup / "bin" / "wannier90.x"
            
            engine = QuantumEspressoEngine(config)
            runner = QECalculationRunner(engine)
            
            working_dir = tmp_path / "work"
            working_dir.mkdir()
            
            input_file = working_dir / "diamond.win"
            input_file.write_text("num_wann = 4\n")
            
            result = runner.run_step(
                input_file=input_file,
                working_dir=working_dir,
                step_type="w90_preproc",
            )
            
            # Verify primary output is <seed>.wout
            expected_output = working_dir / "diamond.wout"
            assert result.output_file == expected_output, \
                f"Primary output should be {expected_output}, got {result.output_file}"
            assert result.output_file.exists(), f"Primary output file {result.output_file} should exist"
            
            # Verify .nnkp exists (required for success)
            nnkp_file = working_dir / "diamond.nnkp"
            assert nnkp_file.exists(), f"Required artifact {nnkp_file} should exist"
            
            # Verify success
            assert result.success is True, f"w90_preproc should succeed when .nnkp exists"
            assert result.return_code == 0
            
            # Verify stdout/stderr capture files exist (using .out/.err naming)
            assert (working_dir / "w90_preproc.out").exists()
            assert (working_dir / "w90_preproc.err").exists()


class TestPipelineReachesPw2Wannier90:
    """Test that the pipeline reaches pw2wannier90 step."""
    
    @pytest.fixture
    def mock_qe_setup(self, tmp_path):
        """Create mock QE installation."""
        mock_qe_home = tmp_path / "qe_home"
        mock_bin = mock_qe_home / "bin"
        mock_bin.mkdir(parents=True)
        (mock_bin / "pw.x").touch()
        
        for exe_name in ["wannier90.x", "pw2wannier90.x"]:
            mock_exe = mock_bin / exe_name
            script_content = """#!/bin/bash
echo "OK" >&1
exit 0
"""
            mock_exe.write_text(script_content)
            mock_exe.chmod(0o755)
        
        return mock_qe_home
    
    def test_pipeline_reaches_pw2wannier90(self, tmp_path, mock_qe_setup):
        """Test that runner reaches pw2wannier90 step."""
        config = EngineConfig(
            name="qe",
            qe_home=mock_qe_setup,
        )
        
        with patch.object(QuantumEspressoEngine, 'get_executable_path') as mock_get_exe:
            def get_exe(executable):
                return mock_qe_setup / "bin" / executable
            mock_get_exe.side_effect = get_exe
            
            engine = QuantumEspressoEngine(config)
            runner = QECalculationRunner(engine)
            
            working_dir = tmp_path / "work"
            working_dir.mkdir()
            
            # Simulate step execution sequence
            # Step 1: w90_preproc
            input_file_preproc = working_dir / "diamond.win"
            input_file_preproc.write_text("num_wann = 4\n")
            # Create .nnkp to simulate success
            (working_dir / "diamond.nnkp").touch()
            (working_dir / "diamond.wout").touch()
            
            result_preproc = runner.run_step(
                input_file=input_file_preproc,
                working_dir=working_dir,
                step_type="w90_preproc",
            )
            
            assert result_preproc.success is True, "w90_preproc should succeed"
            
            # Step 2: pw2wannier90
            input_file_pw2wan = working_dir / "pw2wan.in"
            input_file_pw2wan.write_text("&inputpp\n/\n")
            
            result_pw2wan = runner.run_step(
                input_file=input_file_pw2wan,
                working_dir=working_dir,
                step_type="pw2wannier90",
            )
            
            # Verify pw2wannier90 was executed
            assert result_pw2wan.step_type == "pw2wannier90"
            assert result_pw2wan.return_code == 0
            assert result_pw2wan.success is True
            
            # Verify output files (using .out/.err naming)
            assert (working_dir / "pw2wannier90.out").exists()
            assert (working_dir / "pw2wannier90.err").exists()
            # For pw2wannier90, primary output is the stdout capture
            assert result_pw2wan.output_file == (working_dir / "pw2wannier90.out")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

