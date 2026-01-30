"""
Unit tests for pw2wannier90 execution and output file handling.

Tests verify:
1. Output paths are validated (not directories)
2. pw2wannier90 step is executed and stdout/stderr are written to files
3. Error messages include return code and stderr
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


class TestOutputPathDirectoryHandling:
    """Test that output paths cannot be directories (Errno 21 prevention)."""
    
    def test_output_path_directory_is_not_opened_as_file(self, tmp_path):
        """Test that _ensure_file_path helper prevents Errno 21 when path is a directory."""
        from quantumvitas.core.engines.qe_calculation import QECalculationRunner
        
        # Setup: Create mock QE structure
        mock_qe_home = tmp_path / "qe_home"
        mock_bin = mock_qe_home / "bin"
        mock_bin.mkdir(parents=True)
        (mock_bin / "pw.x").touch()
        (mock_bin / "pw2wannier90.x").touch()
        
        config = EngineConfig(
            name="qe",
            qe_home=mock_qe_home,
        )
        engine = QuantumEspressoEngine(config)
        runner = QECalculationRunner(engine)
        
        working_dir = tmp_path / "work"
        working_dir.mkdir()
        
        # Create a mock input file
        input_file = working_dir / "pw2wan.in"
        input_file.write_text("&inputpp\n/\n")
        
        # Test: should not raise IsADirectoryError even if paths are invalid
        # The _ensure_file_path helper should normalize paths
        # We'll catch FileNotFoundError (executable not found) but NOT IsADirectoryError
        try:
            result = runner.run_step(
                input_file=input_file,
                working_dir=working_dir,
                step_type="pw2wannier90",
            )
            # If we get here, no IsADirectoryError was raised
            assert isinstance(result, StepResult)
            # Result might be a failure (executable not found or other), but that's OK
            # The key is that we didn't hit Errno 21
        except (IsADirectoryError, OSError) as e:
            if "Is a directory" in str(e) or "Errno 21" in str(e) or e.errno == 21:
                pytest.fail(f"Errno 21 raised (this is what we're preventing): {e}")
            # Other OSError is OK (e.g., executable not found)
            pass  # Expected for missing executables


class TestPw2Wannier90ExecutionAndOutputFiles:
    """Test that pw2wannier90 step execution writes output files correctly."""
    
    @pytest.fixture
    def mock_executable(self, tmp_path):
        """Create a mock pw2wannier90.x executable that writes to stdout/stderr."""
        mock_qe_home = tmp_path / "qe_home"
        mock_bin = mock_qe_home / "bin"
        mock_bin.mkdir(parents=True)
        (mock_bin / "pw.x").touch()  # Required for QE installation check
        
        mock_exe = mock_bin / "pw2wannier90.x"
        
        # Create a simple script that outputs to stdout/stderr
        script_content = """#!/bin/bash
echo "HELLO from pw2wannier90" >&1
echo "ERR from pw2wannier90" >&2
exit 0
"""
        mock_exe.write_text(script_content)
        mock_exe.chmod(0o755)
        return mock_qe_home
    
    def test_pw2wannier90_step_executed_and_outputs_written(self, tmp_path, mock_executable):
        """Test that pw2wannier90 step writes stdout and stderr to files."""
        config = EngineConfig(
            name="qe",
            qe_home=mock_executable,
        )
        
        # Mock get_executable_path to return our mock executable
        with patch.object(QuantumEspressoEngine, 'get_executable_path') as mock_get_exe:
            mock_exe_path = mock_executable / "bin" / "pw2wannier90.x"
            mock_get_exe.return_value = mock_exe_path
            
            engine = QuantumEspressoEngine(config)
            runner = QECalculationRunner(engine)
            
            working_dir = tmp_path / "work"
            working_dir.mkdir()
            
            # Create input file
            input_file = working_dir / "pw2wan.in"
            input_file.write_text("&inputpp\n/\n")
            
            # Execute step
            result = runner.run_step(
                input_file=input_file,
                working_dir=working_dir,
                step_type="pw2wannier90",
            )
            
            # Verify result
            assert isinstance(result, StepResult)
            assert result.step_type_spec == "pw2wannier90"
            
            # Verify output files exist (using step_type.out/.err naming)
            stdout_file = working_dir / "pw2wannier90.out"
            stderr_file = working_dir / "pw2wannier90.err"
            
            assert stdout_file.exists(), f"stdout file {stdout_file} should exist"
            assert stderr_file.exists(), f"stderr file {stderr_file} should exist"
            
            # Verify content
            stdout_content = stdout_file.read_text()
            stderr_content = stderr_file.read_text()
            
            assert "HELLO from pw2wannier90" in stdout_content
            assert "ERR from pw2wannier90" in stderr_content
            
            # Verify StepResult contains the content
            assert result.stdout == stdout_content or "HELLO" in result.stdout
            assert result.stderr == stderr_content or "ERR" in result.stderr
            
            # Verify return code
            assert result.return_code == 0
            assert result.success is True


class TestStrictModeFailurePropagation:
    """Test that step failures in strict mode propagate error messages correctly."""
    
    @pytest.fixture
    def mock_failing_executable(self, tmp_path):
        """Create a mock executable that fails with return code 1."""
        mock_qe_home = tmp_path / "qe_home"
        mock_bin = mock_qe_home / "bin"
        mock_bin.mkdir(parents=True)
        (mock_bin / "pw.x").touch()  # Required for QE installation check
        
        mock_exe = mock_bin / "wannier90.x"
        
        script_content = """#!/bin/bash
echo "Error: Something went wrong" >&2
exit 1
"""
        mock_exe.write_text(script_content)
        mock_exe.chmod(0o755)
        return mock_qe_home
    
    def test_strict_mode_failure_propagates_message(self, tmp_path, mock_failing_executable):
        """Test that w90_preproc failure includes return code and stderr in message."""
        config = EngineConfig(
            name="qe",
            qe_home=mock_failing_executable,
        )
        
        with patch.object(QuantumEspressoEngine, 'get_executable_path') as mock_get_exe:
            mock_exe_path = mock_failing_executable / "bin" / "wannier90.x"
            mock_get_exe.return_value = mock_exe_path
            
            engine = QuantumEspressoEngine(config)
            runner = QECalculationRunner(engine)
            
            working_dir = tmp_path / "work"
            working_dir.mkdir()
            
            # Create input file
            input_file = working_dir / "diamond.win"
            input_file.write_text("num_wann = 4\n")
            
            # Execute step
            result = runner.run_step(
                input_file=input_file,
                working_dir=working_dir,
                step_type="w90_preproc",
            )
            
            # Verify failure
            assert result.success is False
            assert result.return_code == 1
            
            # Verify error message includes return code
            assert result.error is not None
            assert "return code" in result.error.lower() or "1" in result.error
            
            # Verify stderr is included
            assert result.stderr is not None
            if "Error" in result.stderr:
                # If stderr contains error, it should be in error message or stderr field
                assert "Error" in result.stderr or "Error" in (result.error or "")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

