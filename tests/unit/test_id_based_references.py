"""
Unit tests for ID-based cross-resource references.

Tests verify that:
- Calculations and steps use structure_ulid (ULID) as canonical references
- Legacy structure selectors (name/slug/path) are still supported
- Resolution prefers structure_ulid over structure selector
- Backwards compatibility is maintained
"""

import tempfile
from pathlib import Path

import pytest
import yaml

from quantumvitas.core.models import CalculationModel, load_calculation, save_calculation
from quantumvitas.core.resources import ResourceMeta, generate_resource_id
from quantumvitas.calculation.structure_steps import StructureStepSpec


class TestCalculationModelStructureReferences:
    """Test CalculationModel structure_ulid vs structure selector."""
    
    def test_calculation_model_with_structure_ulid(self):
        """Test CalculationModel with structure_ulid (new format)."""
        structure_ulid = generate_resource_id()
        structure_name = "Si"
        
        meta = ResourceMeta(ulid=generate_resource_id(),
            name="Test Calculation",
            slug="test-calculation",
            path="calculations/test-calculation",
            kind="calculation",
        )
        
        model = CalculationModel(
            meta=meta,
            structure_ulid=structure_ulid,
            structure_name=structure_name,
        )
        
        # Verify structure_ulid is canonical
        assert model.structure_ulid == structure_ulid
        assert model.structure_name == structure_name
        # structure field removed - no longer exists
        
        # Verify to_dict writes structure_ulid (ID-only reference)
        # DAG + ID-only model: structure_name is NOT written to YAML (cosmetic only)
        data = model.to_dict()
        assert data["structure_ulid"] == structure_ulid
        assert "structure_name" not in data  # structure_name is NOT written (DAG + ID-only model)
        assert "structure" not in data  # Legacy selector NOT written (ID-only model)
    
    def test_calculation_model_from_dict_new_format(self):
        """Test loading CalculationModel from dict with structure_ulid."""
        structure_ulid = generate_resource_id()
        data = {
            "meta": {
                "ulid": generate_resource_id(),
                "name": "Test Calculation",
                "slug": "test-calculation",
                "path": "calculations/test-calculation",
                "kind": "calculation",
            },
            "structure_ulid": structure_ulid,
            "structure_name": "Si",
            "mode": "normal",
            "working_dir": "raw",
            "steps": [],
        }
        
        model = CalculationModel.from_dict(data)
        assert model.structure_ulid == structure_ulid
        assert model.structure_name == "Si"
        # structure field removed - no longer exists
    
    def test_calculation_model_from_dict_legacy_format(self):
        """Test loading CalculationModel from dict with legacy structure selector raises LegacyProjectError."""
        from quantumvitas.core.exceptions import LegacyProjectError
        
        data = {
            "meta": {
                "ulid": generate_resource_id(),
                "name": "Test Calculation",
                "slug": "test-calculation",
                "path": "calculations/test-calculation",
                "kind": "calculation",
            },
            "structure": "si",  # Legacy selector without structure_ulid
            "mode": "normal",
            "working_dir": "raw",
            "steps": [],
        }
        
        # Should raise LegacyProjectError for legacy format
        with pytest.raises(LegacyProjectError) as exc_info:
            CalculationModel.from_dict(data)
        
        assert "structure" in str(exc_info.value).lower() or "legacy" in str(exc_info.value).lower()
    
    def test_calculation_model_load_legacy_selector_raises_error(self, tmp_path):
        """Test that load_calculation raises LegacyProjectError for legacy structure selector."""
        from quantumvitas.core.exceptions import LegacyProjectError
        
        project_root = tmp_path / "project"
        project_root.mkdir()
        
        # Create project.qv.yml with structure
        structure_ulid = generate_resource_id()
        config = {
            "project": {
                "name": "Test Project",
                "meta": {"ulid": generate_resource_id(), "slug": "test-project"},
            },
            "structures": [
                {
                    "name": "Si",
                    "file": "structures/si.json",
                    "meta": {
                        "ulid": structure_ulid,
                        "name": "Si",
                        "slug": "si",
                        "path": "structures/si.json",
                        "kind": "structure",
                    },
                }
            ],
            "calculations": [],
        }
        (project_root / "project.qv.yml").write_text(yaml.safe_dump(config))
        
        # Create calculation.yaml with legacy structure selector (no structure_ulid)
        calculation_dir = project_root / "calculations" / "test-calculation"
        calculation_dir.mkdir(parents=True)
        calculation_yaml = calculation_dir / "calculation.yaml"
        calculation_yaml.write_text(yaml.safe_dump({
            "meta": {
                "ulid": generate_resource_id(),
                "name": "Test Calculation",
                "slug": "test-calculation",
                "path": "calculations/test-calculation",
                "kind": "calculation",
            },
            "structure": "si",  # Legacy selector without structure_ulid
            "mode": "normal",
            "working_dir": "raw",
            "steps": [],
        }))
        
        # Load calculation - should raise LegacyProjectError
        with pytest.raises(LegacyProjectError) as exc_info:
            load_calculation(calculation_yaml, project_root)
        
        assert "structure" in str(exc_info.value).lower() or "legacy" in str(exc_info.value).lower()


class TestStructureStepSpecStructureReferences:
    """Test StructureStepSpec structure_ulid vs structure selector."""
    
    def test_step_spec_with_structure_ulid(self):
        """Test StructureStepSpec with structure_ulid (new format).
        
        DAG + ID-only model: Step YAML must NOT contain structure_ulid or parent_calculation_id.
        Structure is resolved via calculation.structure_ulid at runtime.
        Parent calculation is implicit from step file location.
        """
        structure_ulid = generate_resource_id()
        
        meta = ResourceMeta(ulid=generate_resource_id(),
            name="scf",
            slug="scf",
            path="steps/scf.step.yaml",
            kind="step",
        )
        
        spec = StructureStepSpec(
            meta=meta,
            structure="si",  # Legacy selector for backwards compat (in memory only)
            structure_ulid=structure_ulid,  # In memory only (for backwards compat)
            step_type_spec="qe_scf",
            parent_calculation_id=generate_resource_id(),  # In memory only (for backwards compat)
        )
        
        # Verify structure_ulid is stored in memory (for backwards compat)
        assert spec.structure_ulid == structure_ulid
        assert spec.structure == "si"  # Legacy field preserved in memory
        
        # Verify to_dict does NOT write structure_ulid or parent_calculation_id (DAG invariant)
        data = spec.to_dict()
        assert "structure_ulid" not in data, "Step YAML must NOT contain structure_ulid (DAG model: inherits from calculation)"
        assert "parent_calculation_id" not in data, "Step YAML must NOT contain parent_calculation_id (DAG model: parent is implicit)"
        assert "structure" not in data  # Legacy selector NOT written (DAG model)
    
    def test_step_spec_from_dict_new_format(self):
        """Test loading StructureStepSpec from dict with structure_ulid."""
        structure_ulid = generate_resource_id()
        data = {
            "meta": {
                "ulid": generate_resource_id(),
                "name": "scf",
                "slug": "scf",
                "path": "steps/scf.step.yaml",
                "kind": "step",
            },
            "structure_ulid": structure_ulid,
            "structure": "si",  # Still present for backwards compat
            "step_type_gen": "scf",
            "parent_calculation_id": generate_resource_id(),
        }
        
        spec = StructureStepSpec.from_dict(data)
        assert spec.structure_ulid == structure_ulid
        assert spec.structure == "si"
    
    def test_step_spec_from_dict_legacy_format(self):
        """Test loading StructureStepSpec from dict with legacy structure selector only."""
        data = {
            "meta": {
                "ulid": generate_resource_id(),
                "name": "scf",
                "slug": "scf",
                "path": "steps/scf.step.yaml",
                "kind": "step",
            },
            "structure": "si",  # Legacy selector only
            "step_type_gen": "scf",
            "parent_calculation_id": generate_resource_id(),
        }
        
        spec = StructureStepSpec.from_dict(data)
        assert spec.structure_ulid is None  # Not resolved yet
        assert spec.structure == "si"  # Legacy field preserved
    
    def test_step_spec_does_not_require_structure_or_structure_ulid(self):
        """Test that StructureStepSpec does NOT require structure or structure_ulid.
        
        DAG + ID-only model: Steps inherit structure from calculation.structure_ulid.
        Step YAML does not need to contain structure_ulid or structure selector.
        """
        data = {
            "meta": {
                "ulid": generate_resource_id(),
                "name": "scf",
                "slug": "scf",
                "path": "steps/scf.step.yaml",
                "kind": "step",
            },
            "step_type_gen": "scf",
        }
        
        # Should NOT raise error - structure is resolved from calculation at runtime
        spec = StructureStepSpec.from_dict(data)
        assert spec.structure_ulid is None
        assert spec.structure == ""  # Empty string default


class TestBackwardsCompatibility:
    """Test backwards compatibility with legacy format."""
    
    def test_calculation_yaml_legacy_structure_selector_raises_error(self, tmp_path):
        """Test that calculation.yaml with legacy structure selector raises LegacyProjectError."""
        from quantumvitas.core.exceptions import LegacyProjectError
        
        calculation_dir = tmp_path / "calculation"
        calculation_dir.mkdir()
        calculation_yaml = calculation_dir / "calculation.yaml"
        
        # Write legacy format (structure selector only, no structure_ulid)
        calculation_yaml.write_text(yaml.safe_dump({
            "meta": {
                "ulid": generate_resource_id(),
                "name": "Test Calculation",
                "slug": "test-calculation",
                "path": "calculations/test-calculation",
                "kind": "calculation",
            },
            "structure": "si",  # Legacy selector without structure_ulid
            "mode": "normal",
            "working_dir": "raw",
            "steps": [],
        }))
        
        # Should raise LegacyProjectError
        with pytest.raises(LegacyProjectError) as exc_info:
            CalculationModel.from_dict(yaml.safe_load(calculation_yaml.read_text()))
        
        assert "structure" in str(exc_info.value).lower() or "legacy" in str(exc_info.value).lower()
    
    def test_step_yaml_legacy_structure_selector(self, tmp_path):
        """Test that step.yaml with legacy structure selector still works."""
        step_yaml = tmp_path / "scf.step.yaml"
        
        # Write legacy format (structure selector only)
        step_yaml.write_text(yaml.safe_dump({
            "meta": {
                "ulid": generate_resource_id(),
                "name": "scf",
                "slug": "scf",
                "path": "steps/scf.step.yaml",
                "kind": "step",
            },
            "structure": "si",
            "step_type_gen": "scf",
            "parent_calculation_id": generate_resource_id(),
        }))
        
        # Should load without error (legacy structure selector preserved in memory)
        spec = StructureStepSpec.from_yaml(step_yaml)
        assert spec.structure == "si"  # Legacy selector preserved in memory
        assert spec.structure_ulid is None  # Not resolved without project_root
        
        # When project_root is provided, structure selector should be resolved to structure_ulid
        # (This would require a project with a structure registered, so we test it separately)
    
    def test_calculation_save_only_persists_structure_ulid(self, tmp_path):
        """Test that saving calculation only persists structure_ulid, not structure selector."""
        calculation_dir = tmp_path / "calculation"
        calculation_dir.mkdir()
        calculation_yaml = calculation_dir / "calculation.yaml"
        
        structure_ulid = generate_resource_id()
        meta = ResourceMeta(ulid=generate_resource_id(),
            name="Test Calculation",
            slug="test-calculation",
            path="calculations/test-calculation",
            kind="calculation",
        )
        
        model = CalculationModel(
            meta=meta,
            structure_ulid=structure_ulid,
            structure_name="Si",
        )
        
        save_calculation(model, calculation_yaml)
        
        # Reload and verify only structure_ulid is persisted
        data = yaml.safe_load(calculation_yaml.read_text())
        assert "structure_ulid" in data
        assert data["structure_ulid"] == structure_ulid
        assert "structure" not in data  # Legacy selector NOT written (ID-only model)
        assert "structure_name" not in data  # structure_name is NOT written (cosmetic only)


class TestStructureResolution:
    """Test that structure_ulid is preferred over structure selector."""
    
    def test_resolve_structure_ulid_first(self, tmp_path):
        """Test that _resolve_structure_for_spec prefers structure_ulid."""
        from quantumvitas.project.model import Project
        from quantumvitas.core.resources import meta_from_name
        from quantumvitas.io.structure_io import write_structure
        from pymatgen.core import Structure
        
        project_root = tmp_path / "project"
        project_root.mkdir()
        
        # Create structure
        structure_ulid = generate_resource_id()
        structures_dir = project_root / "structures"
        structures_dir.mkdir()
        structure_file = structures_dir / "si.json"
        
        structure = Structure([[3.84, 0, 0], [0, 3.84, 0], [0, 0, 3.84]], ["Si", "Si"], [[0, 0, 0], [0.25, 0.25, 0.25]])
        meta = meta_from_name("structure", name="Si", path="structures/si.json")
        meta.ulid = structure_ulid
        write_structure(structure, structure_file, metadata=meta)
        
        # Create project
        config = {
            "project": {
                "name": "Test Project",
                "meta": {"ulid": generate_resource_id(), "slug": "test-project"},
            },
            "structures": [
                {
                    "name": "Si",
                    "file": "structures/si.json",
                    "meta": meta.to_dict(),
                }
            ],
            "calculations": [],
        }
        (project_root / "project.qv.yml").write_text(yaml.safe_dump(config))
        
        # Load project using Project.open() method
        project = Project.open(project_root)
        
        # Create step spec with both structure_ulid and structure
        step_meta = ResourceMeta(ulid=generate_resource_id(),
            name="scf",
            slug="scf",
            path="steps/scf.step.yaml",
            kind="step",
        )
        
        spec = StructureStepSpec(
            meta=step_meta,
            structure="wrong",  # Wrong selector
            structure_ulid=structure_ulid,  # Correct ID
            step_type_spec="qe_scf",
        )
        
        # Resolve structure - should use structure_ulid
        from quantumvitas.calculation.structure_steps import _resolve_structure_for_spec
        
        resolved = _resolve_structure_for_spec(
            spec,
            tmp_path / "scf.step.yaml",
            calculation_dir=None,
            project=project,
        )
        
        # Should resolve to correct structure (via structure_ulid, not wrong selector)
        assert resolved is not None

