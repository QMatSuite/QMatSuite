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

