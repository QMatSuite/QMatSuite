"""Unit tests for step artifacts recognition rules."""

import pytest
from pathlib import Path

from quantumvitas.calculation.step_artifacts import (
    get_step_artifacts,
    get_default_artifact,
    _get_wannier90_seedname,
    _get_bands_filband,
)


class TestWannier90Artifacts:
    """Tests for Wannier90 step artifacts recognition."""
    
    def test_w90_preproc_artifacts(self, tmp_path):
        """Test w90_preproc step artifacts."""
        params = {"seedname": "diamond"}
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        
        # Create .nnkp file
        (raw_dir / "diamond.nnkp").write_text("test content")
        
        artifacts = get_step_artifacts("w90_preproc", params, raw_dir)
        assert "diamond.nnkp" in artifacts
        
        # Test default selection
        default = get_default_artifact("w90_preproc", params, raw_dir, artifacts)
        assert default == "diamond.nnkp"
    
    def test_w90_run_artifacts(self, tmp_path):
        """Test w90_run step artifacts."""
        params = {"seedname": "Si"}
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        
        # Create .wout file
        (raw_dir / "Si.wout").write_text("Wannier90 output")
        
        artifacts = get_step_artifacts("w90_run", params, raw_dir)
        assert "Si.wout" in artifacts
        
        # Test default selection (should prefer .wout over .out)
        (raw_dir / "w90_run.out").write_text("stdout")
        all_artifacts = artifacts + ["w90_run.out"]
        default = get_default_artifact("w90_run", params, raw_dir, all_artifacts)
        assert default == "Si.wout"
    
    def test_pw2wannier90_artifacts(self, tmp_path):
        """Test pw2wannier90 step artifacts."""
        params = {"seedname": "test"}
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        
        # Create artifacts
        (raw_dir / "test.amn").write_text("amn content")
        (raw_dir / "test.mmn").write_text("mmn content")
        (raw_dir / "test.eig").write_text("eig content")
        
        artifacts = get_step_artifacts("pw2wannier90", params, raw_dir)
        assert "test.amn" in artifacts
        assert "test.mmn" in artifacts
        assert "test.eig" in artifacts
    
    def test_wannier90_nested_params(self, tmp_path):
        """Test Wannier90 artifacts with nested parameters."""
        # Nested params structure
        params = {
            "inputpp": {
                "seedname": "nested_seed"
            }
        }
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        
        (raw_dir / "nested_seed.wout").write_text("output")
        
        artifacts = get_step_artifacts("w90_run", params, raw_dir)
        assert "nested_seed.wout" in artifacts
    
    def test_wannier90_seedname_extraction(self):
        """Test seedname extraction from various parameter structures."""
        # Flat params
        params1 = {"seedname": "flat"}
        assert _get_wannier90_seedname(params1) == "flat"
        
        # Nested params
        params2 = {"inputpp": {"seedname": "nested"}}
        assert _get_wannier90_seedname(params2) == "nested"
        
        # Missing seedname
        params3 = {"other": "value"}
        assert _get_wannier90_seedname(params3) is None


class TestBandsArtifacts:
    """Tests for bands step artifacts recognition."""
    
    def test_bands_artifacts_with_filband(self, tmp_path):
        """Test bands step artifacts with filband parameter."""
        params = {"filband": "si.bands.dat"}
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        
        # Create artifacts
        (raw_dir / "si.bands.dat").write_text("dat content")
        (raw_dir / "si.bands.dat.gnu").write_text("gnuplot content")
        (raw_dir / "si.bands.dat.rap").write_text("rap content")
        
        artifacts = get_step_artifacts("bands", params, raw_dir)
        assert "si.bands.dat" in artifacts
        assert "si.bands.dat.gnu" in artifacts
        assert "si.bands.dat.rap" in artifacts
        
        # Test default selection (should prefer .gnu)
        all_artifacts = artifacts + ["bands.out"]
        default = get_default_artifact("bands", params, raw_dir, all_artifacts)
        assert default == "si.bands.dat.gnu"
    
    def test_bands_artifacts_nested_params(self, tmp_path):
        """Test bands artifacts with nested BANDS namelist."""
        params = {
            "bands": {
                "filband": "nested.dat"
            }
        }
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        
        (raw_dir / "nested.dat.gnu").write_text("content")
        
        artifacts = get_step_artifacts("bands", params, raw_dir)
        assert "nested.dat.gnu" in artifacts
    
    def test_bands_artifacts_no_filband(self, tmp_path):
        """Test bands artifacts when filband is not specified."""
        params = {}
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        
        # Create files matching common pattern
        (raw_dir / "test.bands.dat").write_text("content")
        (raw_dir / "test.bands.dat.gnu").write_text("content")
        
        artifacts = get_step_artifacts("bands", params, raw_dir)
        # Should find files matching *.bands.dat* pattern
        assert len(artifacts) >= 1
    
    def test_bands_filband_extraction(self):
        """Test filband extraction from various parameter structures."""
        # Top-level filband
        params1 = {"filband": "top.dat"}
        assert _get_bands_filband(params1) == "top.dat"
        
        # Nested in BANDS namelist
        params2 = {"bands": {"filband": "nested.dat"}}
        assert _get_bands_filband(params2) == "nested.dat"
        
        # Missing filband
        params3 = {"other": "value"}
        assert _get_bands_filband(params3) is None


class TestDefaultArtifactSelection:
    """Tests for default artifact selection logic."""
    
    def test_default_prefers_primary_over_stdout(self, tmp_path):
        """Test that primary artifact is preferred over stdout."""
        params = {"seedname": "test"}
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        
        (raw_dir / "test.wout").write_text("primary output")
        (raw_dir / "w90_run.out").write_text("stdout")
        
        artifacts = ["test.wout", "w90_run.out"]
        default = get_default_artifact("w90_run", params, raw_dir, artifacts)
        assert default == "test.wout"
    
    def test_default_fallback_to_stdout(self, tmp_path):
        """Test fallback to stdout when primary artifact missing."""
        params = {"seedname": "missing"}
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        
        (raw_dir / "w90_run.out").write_text("stdout only")
        
        artifacts = ["w90_run.out"]
        default = get_default_artifact("w90_run", params, raw_dir, artifacts)
        assert default == "w90_run.out"
    
    def test_default_skips_empty_files(self, tmp_path):
        """Test that empty files are skipped in default selection."""
        params = {"seedname": "test"}
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        
        # Create empty primary artifact
        (raw_dir / "test.wout").write_text("")  # Empty file
        (raw_dir / "w90_run.out").write_text("stdout content")
        
        artifacts = ["test.wout", "w90_run.out"]
        default = get_default_artifact("w90_run", params, raw_dir, artifacts)
        # Should fallback to stdout if primary is empty
        assert default == "w90_run.out"
    
    def test_default_none_when_no_artifacts(self):
        """Test that None is returned when no artifacts exist."""
        params = {}
        raw_dir = Path("/nonexistent")
        artifacts = []
        
        default = get_default_artifact("unknown_step", params, raw_dir, artifacts)
        assert default is None


class TestStepArtifactsIntegration:
    """Integration tests for step artifacts with actual file structures."""
    
    def test_wannier90_complete_workflow(self, tmp_path):
        """Test artifacts for complete Wannier90 workflow."""
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        
        # Preproc step
        preproc_params = {"seedname": "diamond"}
        (raw_dir / "diamond.nnkp").write_text("nnkp")
        (raw_dir / "w90_preproc.out").write_text("preproc stdout")
        
        preproc_artifacts = get_step_artifacts("w90_preproc", preproc_params, raw_dir)
        assert "diamond.nnkp" in preproc_artifacts
        
        # pw2wannier90 step
        pw2w_params = {"seedname": "diamond"}
        (raw_dir / "diamond.amn").write_text("amn")
        (raw_dir / "diamond.mmn").write_text("mmn")
        (raw_dir / "diamond.eig").write_text("eig")
        
        pw2w_artifacts = get_step_artifacts("pw2wannier90", pw2w_params, raw_dir)
        assert all(f"diamond.{ext}" in pw2w_artifacts for ext in ["amn", "mmn", "eig"])
        
        # w90_run step
        w90_params = {"seedname": "diamond"}
        (raw_dir / "diamond.wout").write_text("wout output")
        
        w90_artifacts = get_step_artifacts("w90_run", w90_params, raw_dir)
        assert "diamond.wout" in w90_artifacts
        
        # Default should be .wout, not .out
        all_artifacts = w90_artifacts + ["w90_run.out"]
        default = get_default_artifact("w90_run", w90_params, raw_dir, all_artifacts)
        assert default == "diamond.wout"

