"""
Unit tests for manifest effective_structure_sha field.
"""

import json
import pytest
from pathlib import Path

from quantumvitas.calculation.manifest import (
    ManifestStepEntry,
    Manifest,
    load_manifest,
)
from quantumvitas.core.exceptions import MissingArtifactError


class TestManifestEffectiveStructureSha:
    """Test effective_structure_sha field in manifest."""

    def test_manifest_entry_has_effective_structure_sha_field(self):
        """ManifestStepEntry has effective_structure_sha field (optional)."""
        entry = ManifestStepEntry(
            kind="scf",
            step_ulid="01TEST",
            pseudo_set_sha="abc123",
            structure_sha="def456",
            step_sha="ghi789",
            effective_structure_sha="jkl012",
        )
        
        assert entry.effective_structure_sha == "jkl012"

    def test_manifest_entry_effective_structure_sha_optional(self):
        """effective_structure_sha can be None (backward compatible)."""
        entry = ManifestStepEntry(
            kind="scf",
            step_ulid="01TEST",
            pseudo_set_sha="abc123",
            structure_sha="def456",
            step_sha="ghi789",
            effective_structure_sha=None,
        )
        
        assert entry.effective_structure_sha is None

    def test_manifest_serialization_includes_effective_structure_sha(self, tmp_path):
        """Manifest serialization includes effective_structure_sha when present."""
        entry = ManifestStepEntry(
            kind="scf",
            step_ulid="01TEST",
            pseudo_set_sha="abc123",
            structure_sha="def456",
            step_sha="ghi789",
            effective_structure_sha="jkl012",
        )
        
        manifest = Manifest(steps=[entry])
        data = manifest.to_dict()
        
        assert "effective_structure_sha" in data["steps"][0]
        assert data["steps"][0]["effective_structure_sha"] == "jkl012"

    def test_manifest_deserialization_backward_compatible(self, tmp_path):
        """Manifest deserialization handles missing effective_structure_sha (backward compatible)."""
        # Simulate old manifest without effective_structure_sha
        old_data = {
            "schema_version": 1,
            "steps": [
                {
                    "kind": "scf",
                    "step_ulid": "01TEST",
                    "pseudo_set_sha": "abc123",
                    "structure_sha": "def456",
                    "step_sha": "ghi789",
                    "done": False,
                }
            ],
        }
        
        manifest = Manifest.from_dict(old_data)
        
        assert len(manifest.steps) == 1
        assert manifest.steps[0].effective_structure_sha is None  # Should default to None

    def test_manifest_deserialization_with_effective_structure_sha(self, tmp_path):
        """Manifest deserialization correctly loads effective_structure_sha when present."""
        data = {
            "schema_version": 1,
            "steps": [
                {
                    "kind": "scf",
                    "step_ulid": "01TEST",
                    "pseudo_set_sha": "abc123",
                    "structure_sha": "def456",
                    "step_sha": "ghi789",
                    "effective_structure_sha": "jkl012",
                    "done": False,
                }
            ],
        }
        
        manifest = Manifest.from_dict(data)
        
        assert manifest.steps[0].effective_structure_sha == "jkl012"


class TestMissingArtifactError:
    """Test MissingArtifactError exception."""

    def test_missing_artifact_error_raises(self):
        """MissingArtifactError can be raised and caught."""
        with pytest.raises(MissingArtifactError) as exc_info:
            raise MissingArtifactError(
                "MISSING_ARTIFACT_ERROR: Step 'scf' requires "
                "the relaxed structure from step 'relax' (ULID: 01RELAX), but "
                "generated_structures/step_01RELAX/current.json is missing."
            )
        
        assert "MISSING_ARTIFACT_ERROR" in str(exc_info.value)
        assert "current.json is missing" in str(exc_info.value)


class TestLoadEffectiveStructure:
    """Test _load_effective_structure_for_step method in executor."""
    
    def test_load_effective_structure_no_relax_before(self, tmp_path):
        """If no relax step before current step, returns (None, None)."""
        from quantumvitas.execution.executor import JobExecutor
        from quantumvitas.calculation.calculation import Calculation
        from quantumvitas.core.resources import ResourceMeta
        from unittest.mock import MagicMock
        
        executor = JobExecutor()
        
        # Create a mock calculation with one SCF step
        calc = MagicMock(spec=Calculation)
        calc.dir = tmp_path / "calc"
        calc.dir.mkdir(parents=True)
        
        step = MagicMock()
        step.meta = ResourceMeta(ulid="01SCF", name="scf", slug="scf", path="steps/scf.step.yaml", kind="step")
        step.step_type_spec= "qe_scf"
        calc.steps = [step]
        
        # Try to load effective structure for step 0 (first step)
        structure, sha = executor._load_effective_structure_for_step(0, calc)
        
        assert structure is None
        assert sha is None
    
    def test_load_effective_structure_missing_artifact_raises(self, tmp_path):
        """If relax step exists but current.json is missing, raises MissingArtifactError."""
        from quantumvitas.execution.executor import JobExecutor
        from quantumvitas.calculation.calculation import Calculation
        from quantumvitas.core.resources import ResourceMeta
        from unittest.mock import MagicMock
        
        executor = JobExecutor()
        
        # Create a mock calculation with relax step followed by SCF step
        calc = MagicMock(spec=Calculation)
        calc.dir = tmp_path / "calc"
        calc.dir.mkdir(parents=True)
        
        relax_step = MagicMock()
        relax_step.meta = ResourceMeta(ulid="01RELAX", name="relax", slug="relax", path="steps/relax.step.yaml", kind="step")
        relax_step.step_type_spec= "qe_relax"
        
        scf_step = MagicMock()
        scf_step.meta = ResourceMeta(ulid="01SCF", name="scf", slug="scf", path="steps/scf.step.yaml", kind="step")
        scf_step.step_type_spec= "qe_scf"
        
        calc.steps = [relax_step, scf_step]
        
        # Try to load effective structure for step 1 (SCF step)
        # Should raise MissingArtifactError because current.json doesn't exist
        with pytest.raises(MissingArtifactError) as exc_info:
            executor._load_effective_structure_for_step(1, calc)
        
        assert "MISSING_ARTIFACT_ERROR" in str(exc_info.value)
        assert "current.json is missing" in str(exc_info.value)
        assert "01RELAX" in str(exc_info.value)
    
    def test_load_effective_structure_success(self, tmp_path):
        """If relax step exists and current.json exists, loads structure and returns SHA."""
        from quantumvitas.execution.executor import JobExecutor
        from quantumvitas.calculation.calculation import Calculation
        from quantumvitas.core.resources import ResourceMeta
        from quantumvitas.execution.relax_artifacts import write_generated_structure
        from pymatgen.core import Structure, Lattice
        from unittest.mock import MagicMock
        
        executor = JobExecutor()
        
        # Create a mock calculation with relax step followed by SCF step
        calc = MagicMock(spec=Calculation)
        calc.dir = tmp_path / "calc"
        calc.dir.mkdir(parents=True)
        
        relax_step = MagicMock()
        relax_step.meta = ResourceMeta(ulid="01RELAX", name="relax", slug="relax", path="steps/relax.step.yaml", kind="step")
        relax_step.step_type_spec= "qe_relax"
        
        scf_step = MagicMock()
        scf_step.meta = ResourceMeta(ulid="01SCF", name="scf", slug="scf", path="steps/scf.step.yaml", kind="step")
        scf_step.step_type_spec= "qe_scf"
        
        calc.steps = [relax_step, scf_step]
        
        # Write a generated structure for the relax step
        lattice = Lattice.cubic(5.5)
        structure = Structure(lattice, ["Si"], [[0, 0, 0]])
        write_generated_structure(
            structure=structure,
            calc_dir=calc.dir,
            step_ulid="01RELAX",
            step_type_spec="qe_relax",  # Execution layer uses SPEC type
        )
        
        # Load effective structure for step 1 (SCF step)
        loaded_structure, sha = executor._load_effective_structure_for_step(1, calc)
        
        assert loaded_structure is not None
        assert len(loaded_structure) == 1
        assert loaded_structure.lattice.a == pytest.approx(5.5)
        assert sha is not None
        assert isinstance(sha, str)
        assert len(sha) > 0


class TestUpdateManifestStepWithEffectiveStructureSha:
    """Test update_manifest_step with effective_structure_sha parameter."""
    
    def test_update_manifest_step_with_effective_structure_sha(self, tmp_path):
        """update_manifest_step accepts and stores effective_structure_sha."""
        from quantumvitas.calculation.manifest import (
            update_manifest_step,
            load_manifest,
            get_manifest_path,
        )
        
        calc_dir = tmp_path / "calc"
        calc_dir.mkdir(parents=True)
        
        # Update manifest step with effective_structure_sha
        update_manifest_step(
            calc_dir=calc_dir,
            step_index=0,
            kind="scf",
            step_ulid="01SCF",
            pseudo_set_sha="abc123",
            structure_sha="def456",
            step_sha="ghi789",
            effective_structure_sha="jkl012",
            done=True,
        )
        
        # Load and verify
        manifest = load_manifest(calc_dir)
        assert manifest is not None
        assert len(manifest.steps) == 1
        assert manifest.steps[0].effective_structure_sha == "jkl012"
    
    def test_update_manifest_step_without_effective_structure_sha(self, tmp_path):
        """update_manifest_step works without effective_structure_sha (backward compatible)."""
        from quantumvitas.calculation.manifest import (
            update_manifest_step,
            load_manifest,
        )
        
        calc_dir = tmp_path / "calc"
        calc_dir.mkdir(parents=True)
        
        # Update manifest step without effective_structure_sha
        update_manifest_step(
            calc_dir=calc_dir,
            step_index=0,
            kind="scf",
            step_ulid="01SCF",
            pseudo_set_sha="abc123",
            structure_sha="def456",
            step_sha="ghi789",
            done=True,
        )
        
        # Load and verify
        manifest = load_manifest(calc_dir)
        assert manifest is not None
        assert len(manifest.steps) == 1
        assert manifest.steps[0].effective_structure_sha is None

