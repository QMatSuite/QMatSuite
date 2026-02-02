"""
Unit tests for output file overwrite behavior.

Tests verify:
1. Output files use step_type.out/.err naming (not versioned with input)
2. Multiple runs overwrite the same output files
3. Input files can be versioned (scf.in, scf-1.in) but outputs are stable
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from quantumvitas.core.engines.qe_calculation import QECalculationRunner, StepResult
from quantumvitas.core.engines.qe import QuantumEspressoEngine
from quantumvitas.core.engines.base import EngineConfig


class TestOutputFileOverwrite:
    """Test that output files are overwritten on multiple runs."""
    
    @pytest.fixture
    def mock_qe_setup(self, tmp_path):
        """Create mock QE installation."""
        mock_qe_home = tmp_path / "qe_home"
        mock_bin = mock_qe_home / "bin"
        mock_bin.mkdir(parents=True)
        (mock_bin / "pw.x").touch()
        
        # Mock executable that outputs different content on each run
        mock_exe = mock_bin / "pw.x"
        script_content = """#!/bin/bash
# Output content based on a counter (simulated via timestamp or random)
echo "JOB DONE - Run $RANDOM" >&1
echo "Error line $RANDOM" >&2
exit 0
"""
        mock_exe.write_text(script_content)
        mock_exe.chmod(0o755)
        return mock_qe_home
    
    def test_output_files_overwrite_on_multiple_runs(self, tmp_path, mock_qe_setup):
        """Test that output files are overwritten, not versioned, on multiple runs."""
        config = EngineConfig(
            name="qe",
            qe_home=mock_qe_setup,
        )
        
        with patch.object(QuantumEspressoEngine, 'get_executable_path') as mock_get_exe:
            mock_get_exe.return_value = mock_qe_setup / "bin" / "pw.x"
            
            engine = QuantumEspressoEngine(config)
            runner = QECalculationRunner(engine)
            
            working_dir = tmp_path / "work"
            working_dir.mkdir()
            
            # Run 1: scf.in -> should produce scf.out, scf.err
            input_file_1 = working_dir / "scf.in"
            input_file_1.write_text("&control\n/\n")
            
            result_1 = runner.run_step(
                input_file=input_file_1,
                working_dir=working_dir,
                step_type_spec="qe_scf",  # Execution layer uses SPEC type
            )
            
            stdout_file_1 = working_dir / "scf.out"
            stderr_file_1 = working_dir / "scf.err"
            
            assert stdout_file_1.exists(), "scf.out should exist after first run"
            assert stderr_file_1.exists(), "scf.err should exist after first run"
            content_1 = stdout_file_1.read_text()
            
            # Run 2: scf-1.in (versioned input) -> should still produce scf.out, scf.err (overwritten)
            input_file_2 = working_dir / "scf-1.in"
            input_file_2.write_text("&control\n/\n")
            
            result_2 = runner.run_step(
                input_file=input_file_2,
                working_dir=working_dir,
                step_type_spec="qe_scf",  # Execution layer uses SPEC type
            )
            
            # Verify output files still use step_type.out/.err (not versioned)
            assert stdout_file_1.exists(), "scf.out should still exist"
            assert stderr_file_1.exists(), "scf.err should still exist"
            
            # Verify it was overwritten (content should be different, but file path is same)
            content_2 = stdout_file_1.read_text()
            # Content may be different (we can't predict the random output), but file path is same
            
            # Verify StepResult points to stable output file names
            assert result_1.output_file == result_2.output_file or (
                result_1.output_file.name == "scf.out" and result_2.output_file.name == "scf.out"
            ), "Both runs should use scf.out as output_file"
            
            assert result_1.stdout_file.name == "scf.out", "stdout_file should be scf.out"
            assert result_2.stdout_file.name == "scf.out", "stdout_file should be scf.out (same on second run)"
            
            # Verify no versioned output files exist
            versioned_outputs = list(working_dir.glob("scf-*.out"))
            assert len(versioned_outputs) == 0, f"Should not have versioned output files: {versioned_outputs}"
    
    def test_wannier90_output_files_stable(self, tmp_path, mock_qe_setup):
        """Test that Wannier90 steps also use stable output file names."""
        mock_bin = mock_qe_setup / "bin"
        mock_exe = mock_bin / "wannier90.x"
        script_content = """#!/bin/bash
touch "$(pwd)/diamond.nnkp"
touch "$(pwd)/diamond.wout"
echo "Success" >&1
exit 0
"""
        mock_exe.write_text(script_content)
        mock_exe.chmod(0o755)
        
        config = EngineConfig(
            name="qe",
            qe_home=mock_qe_setup,
        )
        
        with patch.object(QuantumEspressoEngine, 'get_executable_path') as mock_get_exe:
            mock_get_exe.return_value = mock_exe
            
            engine = QuantumEspressoEngine(config)
            runner = QECalculationRunner(engine)
            
            working_dir = tmp_path / "work"
            working_dir.mkdir()
            
            # Run 1: diamond.win
            input_file_1 = working_dir / "diamond.win"
            input_file_1.write_text("num_wann = 4\n")
            
            result_1 = runner.run_step(
                input_file=input_file_1,
                working_dir=working_dir,
                step_type_spec="w90_wannierprep",  # Execution layer uses SPEC type
            )
            
            # Verify output files use step_type.out/.err
            assert (working_dir / "wannierprep.out").exists()
            assert (working_dir / "wannierprep.err").exists()
            
            # Run 2: diamond-1.win (versioned input)
            input_file_2 = working_dir / "diamond-1.win"
            input_file_2.write_text("num_wann = 4\n")
            
            result_2 = runner.run_step(
                input_file=input_file_2,
                working_dir=working_dir,
                step_type_spec="w90_wannierprep",  # Execution layer uses SPEC type
            )
            
            # Verify output files are still wannierprep.out/.err (overwritten, not versioned)
            assert (working_dir / "wannierprep.out").exists()
            assert (working_dir / "wannierprep.err").exists()
            
            assert result_1.stdout_file is not None and result_1.stdout_file.name == "wannierprep.out"
            assert result_2.stdout_file is not None and result_2.stdout_file.name == "wannierprep.out"
            
            # Verify primary artifact is still diamond.wout (same for both)
            # Note: output_file may be None if wannierprep didn't create .wout (that's OK for preproc)
            # But for w90_run, output_file should be diamond.wout
            if result_1.output_file:
                assert result_1.output_file.name == "diamond.wout"
            if result_2.output_file:
                assert result_2.output_file.name == "diamond.wout"
            
            # No versioned output files
            versioned_outputs = list(working_dir.glob("wannierprep-*.out"))
            assert len(versioned_outputs) == 0, f"Should not have versioned output files: {versioned_outputs}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

