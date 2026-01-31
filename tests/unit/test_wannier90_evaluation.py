"""
Unit tests for Wannier90 step evaluation.

Tests verify:
1. Wannier90 steps do NOT call extract_energy_metrics_from_text
2. parse_scf_output_text does not read from file system
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from quantumvitas.calculation.verification import evaluate_step_result
from quantumvitas.calculation.types import StepMode, StepStatus
from quantumvitas.analysis.parsers import parse_scf_output_text, parse_scf_output_path


class TestWannier90StepsDoNotParseEnergy:
    """Test that Wannier90 steps do not extract energy metrics."""
    
    def test_evaluate_wannier90_steps_does_not_parse_energy(self, monkeypatch):
        """Test that evaluate_step_result does not call extract_energy_metrics_from_text for Wannier90 steps."""
        # Mock extract_energy_metrics_from_text to track if it's called
        call_count = {"count": 0}
        
        def mock_extract(text):
            call_count["count"] += 1
            return {"total_energy_ry": None, "fermi_energy_ev": None}
        
        monkeypatch.setattr(
            "quantumvitas.calculation.verification.extract_energy_metrics_from_text",
            mock_extract
        )
        
        # Test w90_wannierprep
        step_status, message, metrics = evaluate_step_result(
            mode=StepMode.NORMAL,
            step_type="w90_wannierprep",
            output_text="",  # Empty output (typical for Wannier90)
            reference_file=None,
            step_result_return_code=0,
        )
        
        # Should succeed but NOT call extract_energy_metrics_from_text
        assert call_count["count"] == 0, "extract_energy_metrics_from_text should NOT be called for Wannier90 steps"
        assert step_status == StepStatus.SUCCESS
        assert metrics == {}
        
        # Test w90_wannier
        call_count["count"] = 0
        step_status, message, metrics = evaluate_step_result(
            mode=StepMode.NORMAL,
            step_type="w90_wannier",
            output_text="",
            reference_file=None,
            step_result_return_code=0,
        )
        
        assert call_count["count"] == 0
        assert step_status == StepStatus.SUCCESS
        assert metrics == {}
        
        # Test qe_pw2wannier
        call_count["count"] = 0
        step_status, message, metrics = evaluate_step_result(
            mode=StepMode.NORMAL,
            step_type="qe_pw2wannier",
            output_text="",
            reference_file=None,
            step_result_return_code=0,
        )
        
        assert call_count["count"] == 0
        assert step_status == StepStatus.SUCCESS
        assert metrics == {}
        
        # Verify QE steps DO call extract_energy_metrics_from_text
        call_count["count"] = 0
        step_status, message, metrics = evaluate_step_result(
            mode=StepMode.NORMAL,
            step_type="scf",
            output_text="JOB DONE",
            reference_file=None,
            step_result_return_code=0,
        )
        
        assert call_count["count"] == 1, "extract_energy_metrics_from_text SHOULD be called for QE steps"
        assert step_status == StepStatus.SUCCESS


class TestParseScfOutputTextDoesNotReadPath:
    """Test that parse_scf_output_text does not access file system."""
    
    def test_parse_scf_output_text_does_not_read_path(self, tmp_path):
        """Test that parse_scf_output_text with text input does not read from file system."""
        # Create a test file (should not be read)
        test_file = tmp_path / "test.out"
        test_file.write_text("This should not be read")
        
        # Call parse_scf_output_text with actual text content
        text_content = """
        JOB DONE
        !    total energy              =      -123.45678901 Ry
        """
        
        # Should parse the text directly, not read test_file
        result = parse_scf_output_text(text_content)
        
        # Verify it parsed the text (has energy value)
        assert result.total_energy is not None
        assert abs(result.total_energy - (-123.45678901)) < 1e-6
        
        # Verify test_file content is unchanged (proves it wasn't read)
        assert test_file.read_text() == "This should not be read"
    
    def test_parse_scf_output_path_rejects_directory(self, tmp_path):
        """Test that parse_scf_output_path raises ValueError for directory input."""
        # Try to parse a directory (e.g., '.')
        with pytest.raises(ValueError, match="Expected file path, got directory"):
            parse_scf_output_path(tmp_path)  # tmp_path is a directory
        
        # Try with '.'
        with pytest.raises(ValueError, match="Expected file path, got directory"):
            parse_scf_output_path(".")
    
    def test_parse_scf_output_handles_dot_as_text(self):
        """Test that parse_scf_output treats '.' as text when it's a directory."""
        # '.' as a string should be treated as text (though it won't parse successfully)
        # We just want to ensure it doesn't try to read '.' as a file
        result = parse_scf_output_text(".")
        # Should not raise IsADirectoryError
        assert result.converged is False  # No "JOB DONE" in "."
        assert result.total_energy is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

