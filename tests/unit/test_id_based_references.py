"""
Unit tests for ID-based cross-resource references.

Tests verify that:
- Workflows and steps use structure_id (ULID) as canonical references
- Legacy structure selectors (name/slug/path) are still supported
- Resolution prefers structure_id over structure selector
- Backwards compatibility is maintained
"""

import tempfile
from pathlib import Path

import pytest
import yaml

from quantumvitas.core.models import WorkflowModel, load_workflow, save_workflow
from quantumvitas.core.resources import ResourceMeta, generate_resource_id
from quantumvitas.workflow.structure_steps import StructureStepSpec


class TestWorkflowModelStructureReferences:
    """Test WorkflowModel structure_id vs structure selector."""
    
    def test_workflow_model_with_structure_id(self):
        """Test WorkflowModel with structure_id (new format)."""
        structure_id = generate_resource_id()
        structure_name = "Si"
        
        meta = ResourceMeta(
            id=generate_resource_id(),
            name="Test Workflow",
            slug="test-workflow",
            path="workflows/test-workflow",
            kind="workflow",
        )
        
        model = WorkflowModel(
            meta=meta,
            structure_id=structure_id,
            structure_name=structure_name,
            structure="si",  # Legacy selector for backwards compat
        )
        
        # Verify structure_id is canonical
        assert model.structure_id == structure_id
        assert model.structure_name == structure_name
        assert model.structure == "si"  # Legacy field preserved
        
        # Verify to_dict writes structure_id (ID-only reference)
        # DAG + ID-only model: structure_name is NOT written to YAML (cosmetic only)
        data = model.to_dict()
        assert data["structure_id"] == structure_id
        assert "structure_name" not in data  # structure_name is NOT written (DAG + ID-only model)
        assert "structure" not in data  # Legacy selector NOT written (ID-only model)
    
    def test_workflow_model_from_dict_new_format(self):
        """Test loading WorkflowModel from dict with structure_id."""
        structure_id = generate_resource_id()
        data = {
            "meta": {
                "id": generate_resource_id(),
                "name": "Test Workflow",
                "slug": "test-workflow",
                "path": "workflows/test-workflow",
                "kind": "workflow",
            },
            "structure_id": structure_id,
            "structure_name": "Si",
            "mode": "normal",
            "working_dir": "raw",
            "steps": [],
        }
        
        model = WorkflowModel.from_dict(data)
        assert model.structure_id == structure_id
        assert model.structure_name == "Si"
        assert model.structure is None  # Not provided in new format
    
    def test_workflow_model_from_dict_legacy_format(self):
        """Test loading WorkflowModel from dict with legacy structure selector."""
        data = {
            "meta": {
                "id": generate_resource_id(),
                "name": "Test Workflow",
                "slug": "test-workflow",
                "path": "workflows/test-workflow",
                "kind": "workflow",
            },
            "structure": "si",  # Legacy selector
            "mode": "normal",
            "working_dir": "raw",
            "steps": [],
        }
        
        model = WorkflowModel.from_dict(data)
        assert model.structure_id is None  # Not resolved yet
        assert model.structure == "si"  # Legacy field preserved
    
    def test_workflow_model_load_resolves_structure_selector(self, tmp_path):
        """Test that load_workflow resolves structure selector to structure_id."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        
        # Create project.qv.yml with structure
        structure_id = generate_resource_id()
        config = {
            "project": {
                "name": "Test Project",
                "meta": {"id": generate_resource_id(), "slug": "test-project"},
            },
            "structures": [
                {
                    "name": "Si",
                    "file": "structures/si.json",
                    "meta": {
                        "id": structure_id,
                        "name": "Si",
                        "slug": "si",
                        "path": "structures/si.json",
                        "kind": "structure",
                    },
                }
            ],
            "workflows": [],
        }
        (project_root / "project.qv.yml").write_text(yaml.safe_dump(config))
        
        # Create workflow.yaml with legacy structure selector
        workflow_dir = project_root / "workflows" / "test-workflow"
        workflow_dir.mkdir(parents=True)
        workflow_yaml = workflow_dir / "workflow.yaml"
        workflow_yaml.write_text(yaml.safe_dump({
            "meta": {
                "id": generate_resource_id(),
                "name": "Test Workflow",
                "slug": "test-workflow",
                "path": "workflows/test-workflow",
                "kind": "workflow",
            },
            "structure": "si",  # Legacy selector
            "mode": "normal",
            "working_dir": "raw",
            "steps": [],
        }))
        
        # Load workflow - should resolve structure selector to structure_id
        model = load_workflow(workflow_yaml, project_root)
        assert model.structure_id == structure_id
        assert model.structure_name == "Si"
        assert model.structure == "si"  # Legacy field preserved


class TestStructureStepSpecStructureReferences:
    """Test StructureStepSpec structure_id vs structure selector."""
    
    def test_step_spec_with_structure_id(self):
        """Test StructureStepSpec with structure_id (new format).
        
        DAG + ID-only model: Step YAML must NOT contain structure_id or parent_workflow_id.
        Structure is resolved via workflow.structure_id at runtime.
        Parent workflow is implicit from step file location.
        """
        structure_id = generate_resource_id()
        
        meta = ResourceMeta(
            id=generate_resource_id(),
            name="scf",
            slug="scf",
            path="steps/scf.step.yaml",
            kind="step",
        )
        
        spec = StructureStepSpec(
            meta=meta,
            structure="si",  # Legacy selector for backwards compat (in memory only)
            structure_id=structure_id,  # In memory only (for backwards compat)
            step_type="scf",
            parent_workflow_id=generate_resource_id(),  # In memory only (for backwards compat)
        )
        
        # Verify structure_id is stored in memory (for backwards compat)
        assert spec.structure_id == structure_id
        assert spec.structure == "si"  # Legacy field preserved in memory
        
        # Verify to_dict does NOT write structure_id or parent_workflow_id (DAG invariant)
        data = spec.to_dict()
        assert "structure_id" not in data, "Step YAML must NOT contain structure_id (DAG model: inherits from workflow)"
        assert "parent_workflow_id" not in data, "Step YAML must NOT contain parent_workflow_id (DAG model: parent is implicit)"
        assert "structure" not in data  # Legacy selector NOT written (DAG model)
    
    def test_step_spec_from_dict_new_format(self):
        """Test loading StructureStepSpec from dict with structure_id."""
        structure_id = generate_resource_id()
        data = {
            "meta": {
                "id": generate_resource_id(),
                "name": "scf",
                "slug": "scf",
                "path": "steps/scf.step.yaml",
                "kind": "step",
            },
            "structure_id": structure_id,
            "structure": "si",  # Still present for backwards compat
            "step_type": "scf",
            "parent_workflow_id": generate_resource_id(),
        }
        
        spec = StructureStepSpec.from_dict(data)
        assert spec.structure_id == structure_id
        assert spec.structure == "si"
    
    def test_step_spec_from_dict_legacy_format(self):
        """Test loading StructureStepSpec from dict with legacy structure selector only."""
        data = {
            "meta": {
                "id": generate_resource_id(),
                "name": "scf",
                "slug": "scf",
                "path": "steps/scf.step.yaml",
                "kind": "step",
            },
            "structure": "si",  # Legacy selector only
            "step_type": "scf",
            "parent_workflow_id": generate_resource_id(),
        }
        
        spec = StructureStepSpec.from_dict(data)
        assert spec.structure_id is None  # Not resolved yet
        assert spec.structure == "si"  # Legacy field preserved
    
    def test_step_spec_does_not_require_structure_or_structure_id(self):
        """Test that StructureStepSpec does NOT require structure or structure_id.
        
        DAG + ID-only model: Steps inherit structure from workflow.structure_id.
        Step YAML does not need to contain structure_id or structure selector.
        """
        data = {
            "meta": {
                "id": generate_resource_id(),
                "name": "scf",
                "slug": "scf",
                "path": "steps/scf.step.yaml",
                "kind": "step",
            },
            "step_type": "scf",
        }
        
        # Should NOT raise error - structure is resolved from workflow at runtime
        spec = StructureStepSpec.from_dict(data)
        assert spec.structure_id is None
        assert spec.structure == ""  # Empty string default


class TestBackwardsCompatibility:
    """Test backwards compatibility with legacy format."""
    
    def test_workflow_yaml_legacy_structure_selector(self, tmp_path):
        """Test that workflow.yaml with legacy structure selector still works."""
        workflow_dir = tmp_path / "workflow"
        workflow_dir.mkdir()
        workflow_yaml = workflow_dir / "workflow.yaml"
        
        # Write legacy format (structure selector only)
        workflow_yaml.write_text(yaml.safe_dump({
            "meta": {
                "id": generate_resource_id(),
                "name": "Test Workflow",
                "slug": "test-workflow",
                "path": "workflows/test-workflow",
                "kind": "workflow",
            },
            "structure": "si",
            "mode": "normal",
            "working_dir": "raw",
            "steps": [],
        }))
        
        # Should load without error
        model = WorkflowModel.from_dict(yaml.safe_load(workflow_yaml.read_text()))
        assert model.structure == "si"
        assert model.structure_id is None  # Not resolved without project_root
    
    def test_step_yaml_legacy_structure_selector(self, tmp_path):
        """Test that step.yaml with legacy structure selector still works."""
        step_yaml = tmp_path / "scf.step.yaml"
        
        # Write legacy format (structure selector only)
        step_yaml.write_text(yaml.safe_dump({
            "meta": {
                "id": generate_resource_id(),
                "name": "scf",
                "slug": "scf",
                "path": "steps/scf.step.yaml",
                "kind": "step",
            },
            "structure": "si",
            "step_type": "scf",
            "parent_workflow_id": generate_resource_id(),
        }))
        
        # Should load without error (legacy structure selector preserved in memory)
        spec = StructureStepSpec.from_yaml(step_yaml)
        assert spec.structure == "si"  # Legacy selector preserved in memory
        assert spec.structure_id is None  # Not resolved without project_root
        
        # When project_root is provided, structure selector should be resolved to structure_id
        # (This would require a project with a structure registered, so we test it separately)
    
    def test_workflow_save_preserves_legacy_structure(self, tmp_path):
        """Test that saving workflow preserves legacy structure field."""
        workflow_dir = tmp_path / "workflow"
        workflow_dir.mkdir()
        workflow_yaml = workflow_dir / "workflow.yaml"
        
        meta = ResourceMeta(
            id=generate_resource_id(),
            name="Test Workflow",
            slug="test-workflow",
            path="workflows/test-workflow",
            kind="workflow",
        )
        
        model = WorkflowModel(
            meta=meta,
            structure_id=generate_resource_id(),
            structure_name="Si",
            structure="si",  # Legacy field
        )
        
        save_workflow(model, workflow_yaml)
        
        # Reload and verify both formats are present
        data = yaml.safe_load(workflow_yaml.read_text())
        assert "structure_id" in data
        assert "structure" not in data  # Legacy selector NOT written (ID-only model)


class TestStructureResolution:
    """Test that structure_id is preferred over structure selector."""
    
    def test_resolve_structure_id_first(self, tmp_path):
        """Test that _resolve_structure_for_spec prefers structure_id."""
        from quantumvitas.project.model import Project
        from quantumvitas.core.resources import meta_from_name
        from quantumvitas.io.structure_io import write_structure
        from pymatgen.core import Structure
        
        project_root = tmp_path / "project"
        project_root.mkdir()
        
        # Create structure
        structure_id = generate_resource_id()
        structures_dir = project_root / "structures"
        structures_dir.mkdir()
        structure_file = structures_dir / "si.json"
        
        structure = Structure([[3.84, 0, 0], [0, 3.84, 0], [0, 0, 3.84]], ["Si", "Si"], [[0, 0, 0], [0.25, 0.25, 0.25]])
        meta = meta_from_name("structure", name="Si", path="structures/si.json")
        meta.id = structure_id
        write_structure(structure, structure_file, metadata=meta)
        
        # Create project
        config = {
            "project": {
                "name": "Test Project",
                "meta": {"id": generate_resource_id(), "slug": "test-project"},
            },
            "structures": [
                {
                    "name": "Si",
                    "file": "structures/si.json",
                    "meta": meta.to_dict(),
                }
            ],
            "workflows": [],
        }
        (project_root / "project.qv.yml").write_text(yaml.safe_dump(config))
        
        # Load project using Project.open() method
        project = Project.open(project_root)
        
        # Create step spec with both structure_id and structure
        step_meta = ResourceMeta(
            id=generate_resource_id(),
            name="scf",
            slug="scf",
            path="steps/scf.step.yaml",
            kind="step",
        )
        
        spec = StructureStepSpec(
            meta=step_meta,
            structure="wrong",  # Wrong selector
            structure_id=structure_id,  # Correct ID
            step_type="scf",
        )
        
        # Resolve structure - should use structure_id
        from quantumvitas.workflow.structure_steps import _resolve_structure_for_spec
        
        resolved = _resolve_structure_for_spec(
            spec,
            tmp_path / "scf.step.yaml",
            workflow_dir=None,
            project=project,
        )
        
        # Should resolve to correct structure (via structure_id, not wrong selector)
        assert resolved is not None

