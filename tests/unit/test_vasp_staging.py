"""Unit tests for VASP artifact staging."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from qmatsuite.execution.vasp_staging import (
    stage_chgcar,
    stage_wavecar,
    is_scf_step,
    MissingPrerequisiteError,
    MissingArtifactError,
)
from qmatsuite.calculation.manifest import ManifestStepEntry


class MockStep:
    """Mock step for testing."""
    def __init__(self, step_type_spec: str, step_id: str = "01TEST"):
        self.step_type_spec = step_type_spec  # SPEC type (e.g., "vasp_scf")
        # Extract GEN type from SPEC type
        self.step_type_gen = step_type_spec.split("_", 1)[-1] if "_" in step_type_spec else step_type_spec
        self.meta = Mock()
        self.meta.ulid = step_id


class TestVASPStaging:
    """Test VASP artifact staging logic."""
    
    def test_is_scf_step(self):
        """Test is_scf_step helper."""
        scf_step = MockStep("vasp_scf")
        assert is_scf_step(scf_step) is True
        
        bands_step = MockStep("vasp_bandspw")
        assert is_scf_step(bands_step) is False
    
    def test_stage_chgcar_non_scf_with_done_and_file(self, tmp_path):
        """Test non-SCF step with done=True and file exists → copy."""
        calc_raw_dir = tmp_path / "calc" / "raw"
        calc_raw_dir.mkdir(parents=True)
        
        ref_workdir = calc_raw_dir / "ref_scf_id"
        ref_workdir.mkdir()
        chgcar_src = ref_workdir / "CHGCAR"
        chgcar_src.write_text("fake CHGCAR content")
        
        target_workdir = calc_raw_dir / "current_step_id"
        target_workdir.mkdir()
        
        current_step = MockStep("vasp_bandspw", "current_step_id")
        ref_step = MockStep("vasp_scf", "ref_scf_id")
        manifest_entry = ManifestStepEntry(
            kind="scf",
            step_ulid="ref_scf_id",
            pseudo_set_sha="abc123",
            structure_sha="def456",
            step_sha="ghi789",
            done=True,
        )
        
        stage_chgcar(
            current_step, ref_step, manifest_entry, calc_raw_dir, target_workdir
        )
        
        chgcar_dst = target_workdir / "CHGCAR"
        assert chgcar_dst.exists()
        assert chgcar_dst.read_text() == "fake CHGCAR content"
    
    def test_stage_chgcar_non_scf_with_done_false(self, tmp_path):
        """Test non-SCF step with done=False → MissingPrerequisiteError."""
        calc_raw_dir = tmp_path / "calc" / "raw"
        calc_raw_dir.mkdir(parents=True)
        
        target_workdir = calc_raw_dir / "current_step_id"
        target_workdir.mkdir()
        
        current_step = MockStep("vasp_bandspw", "current_step_id")
        ref_step = MockStep("vasp_scf", "ref_scf_id")
        manifest_entry = ManifestStepEntry(
            kind="scf",
            step_ulid="ref_scf_id",
            pseudo_set_sha="abc123",
            structure_sha="def456",
            step_sha="ghi789",
            done=False,  # Not done
        )
        
        with pytest.raises(MissingPrerequisiteError, match="not done"):
            stage_chgcar(
                current_step, ref_step, manifest_entry, calc_raw_dir, target_workdir
            )
    
    def test_stage_chgcar_non_scf_with_file_missing(self, tmp_path):
        """Test non-SCF step with done=True but file missing → MissingArtifactError."""
        calc_raw_dir = tmp_path / "calc" / "raw"
        calc_raw_dir.mkdir(parents=True)
        
        ref_workdir = calc_raw_dir / "ref_scf_id"
        ref_workdir.mkdir()
        # CHGCAR not created
        
        target_workdir = calc_raw_dir / "current_step_id"
        target_workdir.mkdir()
        
        current_step = MockStep("vasp_bandspw", "current_step_id")
        ref_step = MockStep("vasp_scf", "ref_scf_id")
        manifest_entry = ManifestStepEntry(
            kind="scf",
            step_ulid="ref_scf_id",
            pseudo_set_sha="abc123",
            structure_sha="def456",
            step_sha="ghi789",
            done=True,
        )
        
        with pytest.raises(MissingArtifactError, match="CHGCAR not found"):
            stage_chgcar(
                current_step, ref_step, manifest_entry, calc_raw_dir, target_workdir
            )
    
    def test_stage_chgcar_scf_with_done_false(self, tmp_path):
        """Test SCF step with done=False → skip silently."""
        calc_raw_dir = tmp_path / "calc" / "raw"
        calc_raw_dir.mkdir(parents=True)
        
        target_workdir = calc_raw_dir / "current_step_id"
        target_workdir.mkdir()
        
        current_step = MockStep("vasp_scf", "current_step_id")
        ref_step = MockStep("vasp_scf", "ref_scf_id")
        manifest_entry = ManifestStepEntry(
            kind="scf",
            step_ulid="ref_scf_id",
            pseudo_set_sha="abc123",
            structure_sha="def456",
            step_sha="ghi789",
            done=False,  # Not done
        )
        
        # Should not raise, should skip silently
        stage_chgcar(
            current_step, ref_step, manifest_entry, calc_raw_dir, target_workdir
        )
        
        chgcar_dst = target_workdir / "CHGCAR"
        assert not chgcar_dst.exists()  # Not copied
    
    def test_stage_chgcar_scf_with_file_missing(self, tmp_path):
        """Test SCF step with done=True but file missing → skip silently."""
        calc_raw_dir = tmp_path / "calc" / "raw"
        calc_raw_dir.mkdir(parents=True)
        
        ref_workdir = calc_raw_dir / "ref_scf_id"
        ref_workdir.mkdir()
        # CHGCAR not created
        
        target_workdir = calc_raw_dir / "current_step_id"
        target_workdir.mkdir()
        
        current_step = MockStep("vasp_scf", "current_step_id")
        ref_step = MockStep("vasp_scf", "ref_scf_id")
        manifest_entry = ManifestStepEntry(
            kind="scf",
            step_ulid="ref_scf_id",
            pseudo_set_sha="abc123",
            structure_sha="def456",
            step_sha="ghi789",
            done=True,
        )
        
        # Should not raise, should skip silently
        stage_chgcar(
            current_step, ref_step, manifest_entry, calc_raw_dir, target_workdir
        )
        
        chgcar_dst = target_workdir / "CHGCAR"
        assert not chgcar_dst.exists()  # Not copied
    
    def test_stage_wavecar_success(self, tmp_path):
        """Test WAVECAR staging success."""
        calc_raw_dir = tmp_path / "calc" / "raw"
        calc_raw_dir.mkdir(parents=True)
        
        ref_workdir = calc_raw_dir / "ref_scf_id"
        ref_workdir.mkdir()
        wavecar_src = ref_workdir / "WAVECAR"
        wavecar_src.write_text("fake WAVECAR content")
        
        target_workdir = calc_raw_dir / "current_step_id"
        target_workdir.mkdir()
        
        current_step = MockStep("vasp_bandspw", "current_step_id")
        ref_step = MockStep("vasp_scf", "ref_scf_id")
        manifest_entry = ManifestStepEntry(
            kind="scf",
            step_ulid="ref_scf_id",
            pseudo_set_sha="abc123",
            structure_sha="def456",
            step_sha="ghi789",
            done=True,
        )
        
        result = stage_wavecar(
            current_step, ref_step, manifest_entry, calc_raw_dir, target_workdir
        )
        
        assert result is True
        wavecar_dst = target_workdir / "WAVECAR"
        assert wavecar_dst.exists()
        assert wavecar_dst.read_text() == "fake WAVECAR content"
    
    def test_stage_wavecar_optional_failure(self, tmp_path):
        """Test WAVECAR staging failure (optional) → returns False."""
        calc_raw_dir = tmp_path / "calc" / "raw"
        calc_raw_dir.mkdir(parents=True)
        
        ref_workdir = calc_raw_dir / "ref_scf_id"
        ref_workdir.mkdir()
        # WAVECAR not created
        
        target_workdir = calc_raw_dir / "current_step_id"
        target_workdir.mkdir()
        
        current_step = MockStep("vasp_bandspw", "current_step_id")
        ref_step = MockStep("vasp_scf", "ref_scf_id")
        manifest_entry = ManifestStepEntry(
            kind="scf",
            step_ulid="ref_scf_id",
            pseudo_set_sha="abc123",
            structure_sha="def456",
            step_sha="ghi789",
            done=True,
        )
        
        result = stage_wavecar(
            current_step, ref_step, manifest_entry, calc_raw_dir, target_workdir
        )
        
        assert result is False
        wavecar_dst = target_workdir / "WAVECAR"
        assert not wavecar_dst.exists()
    
    def test_stage_wavecar_required_failure(self, tmp_path):
        """Test WAVECAR staging failure (required=True) → raises error."""
        calc_raw_dir = tmp_path / "calc" / "raw"
        calc_raw_dir.mkdir(parents=True)
        
        ref_workdir = calc_raw_dir / "ref_scf_id"
        ref_workdir.mkdir()
        # WAVECAR not created
        
        target_workdir = calc_raw_dir / "current_step_id"
        target_workdir.mkdir()
        
        current_step = MockStep("vasp_bandspw", "current_step_id")
        ref_step = MockStep("vasp_scf", "ref_scf_id")
        manifest_entry = ManifestStepEntry(
            kind="scf",
            step_ulid="ref_scf_id",
            pseudo_set_sha="abc123",
            structure_sha="def456",
            step_sha="ghi789",
            done=True,
        )
        
        with pytest.raises(MissingArtifactError, match="WAVECAR not found"):
            stage_wavecar(
                current_step, ref_step, manifest_entry, calc_raw_dir, target_workdir,
                required=True
            )

