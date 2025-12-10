"""
Test that QVService APIs handle legacy workflows with non-ULID step IDs.

This ensures that GUI workflows view works with old demo projects that have
step_id: "scf" instead of step_id: "01ULID_HERE".
"""

import json
import yaml
from pathlib import Path

import pytest

from quantumvitas.api import QVService
from quantumvitas.core.resources import generate_resource_id, meta_from_name


@pytest.fixture
def legacy_workflow_project(tmp_path: Path) -> Path:
    """Create a project with a legacy workflow (step_id is name, not ULID)."""
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    
    # Create a structure for the workflow
    structure_id = generate_resource_id()
    structure_meta = meta_from_name("structure", name="test_structure", path="structures/test_structure.json")
    structure_meta.id = structure_id
    
    structures_dir = project_root / "structures"
    structures_dir.mkdir(parents=True, exist_ok=True)
    from quantumvitas.io.structure_io import STRUCTURE_META_KEY, STRUCTURE_DATA_KEY
    structure_json = {
        STRUCTURE_META_KEY: structure_meta.to_dict(),
        STRUCTURE_DATA_KEY: {
            "@module": "pymatgen.core.structure",
            "@class": "Structure",
            "lattice": {"matrix": [[5.43, 0.0, 0.0], [0.0, 5.43, 0.0], [0.0, 0.0, 5.43]]},
            "sites": [{"species": [{"element": "Si", "occu": 1}], "abc": [0.0, 0.0, 0.0]}],
        },
    }
    (structures_dir / "test_structure.json").write_text(json.dumps(structure_json, indent=2))
    
    # Create project.qv.yml
    # Generate workflow ULID first, then use it in both id and meta.id
    workflow_ulid = generate_resource_id()
    project_config = {
        "project": {
            "name": "test_project",
            "meta": {
                "id": generate_resource_id(),
                "name": "test_project",
                "slug": "test_project",
                "path": ".",
                "kind": "project",
            },
        },
        "structures": [
            {
                "id": structure_id,
                "file": "structures/test_structure.json",
                "meta": structure_meta.to_dict(),
            }
        ],
        "workflows": [
            {
                "id": workflow_ulid,  # Use ULID, not human-readable name
                "path": "workflows/test_workflow",
                "meta": {
                    "id": workflow_ulid,  # Same ULID as id field
                    "name": "test_workflow",
                    "slug": "test_workflow",
                    "path": "workflows/test_workflow",
                    "kind": "workflow",
                },
            }
        ],
    }
    (project_root / "project.qv.yml").write_text(yaml.safe_dump(project_config, sort_keys=False))
    
    # Create workflow directory
    workflow_dir = project_root / "workflows" / "test_workflow"
    workflow_dir.mkdir(parents=True)
    (workflow_dir / "raw").mkdir()
    (workflow_dir / "steps").mkdir()
    
    # Create a step file with ULID meta.id
    step_ulid = generate_resource_id()
    step_file = workflow_dir / "steps" / "scf.step.yaml"
    step_meta = meta_from_name("step", name="scf", path="workflows/test_workflow/steps/scf.step.yaml")
    step_meta.id = step_ulid
    
    # DAG model: Step YAML should NOT contain structure_id (inherits from workflow)
    step_spec = {
        "meta": step_meta.to_dict(),
        "step_type": "scf",
        # structure_id is NOT in step YAML (DAG model)
    }
    step_file.write_text(yaml.safe_dump(step_spec, sort_keys=False))
    
    # Create legacy workflow.yaml with step_id as name (not ULID) and structure selector
    # Note: This is a legacy test, so we use legacy format but ensure workflow has proper meta
    workflow_yaml = {
        "meta": {
            "id": workflow_ulid,  # Use the ULID from project_config
            "name": "test_workflow",
            "slug": "test_workflow",
            "path": "workflows/test_workflow",
            "kind": "workflow",
        },
        "id": "test_workflow",  # Legacy field (kept for backwards compat)
        "mode": "normal",
        "workflow": {"working_dir": "raw"},
        "structure": "test_structure",  # Legacy structure selector
        "structure_id": structure_id,  # Also include structure_id (ULID) for migration
        "steps": [
            {
                "id": "scf",  # Legacy: name instead of ULID
                "step_id": "scf",  # Also legacy: should be ULID
                "type": "scf",
                "input": "raw/scf.in",
            }
        ],
    }
    (workflow_dir / "workflow.yaml").write_text(yaml.safe_dump(workflow_yaml, sort_keys=False))
    
    return project_root


def test_list_workflows_data_handles_legacy_step_ids(legacy_workflow_project: Path):
    """Test that list_workflows_data successfully loads legacy workflows."""
    workflows = QVService.list_workflows_data(legacy_workflow_project)
    
    assert len(workflows) == 1
    workflow = workflows[0]
    
    assert workflow["name"] == "test_workflow"
    assert workflow["n_steps"] == 1
    
    # After migration, step_id should be ULID (not "scf")
    steps = workflow["steps"]
    assert len(steps) == 1
    step = steps[0]
    
    # step_id should be a ULID (26 characters)
    assert len(step["step_id"]) == 26
    assert step["step_id"] != "scf"  # Should be migrated to ULID
    assert step["type"] == "scf"


def test_get_workflow_detail_handles_legacy_step_ids(legacy_workflow_project: Path):
    """Test that get_workflow_detail successfully loads legacy workflows."""
    detail = QVService.get_workflow_detail(legacy_workflow_project, "test_workflow")
    
    assert detail["name"] == "test_workflow"
    assert detail["n_steps"] == 1
    
    # After migration, step_id should be ULID (not "scf")
    steps = detail["steps"]
    assert len(steps) == 1
    step = steps[0]
    
    # step_id should be a ULID (26 characters)
    assert len(step["step_id"]) == 26
    assert step["step_id"] != "scf"  # Should be migrated to ULID
    assert step["type"] == "scf"


def test_legacy_workflow_auto_migrated_on_disk(legacy_workflow_project: Path):
    """Test that legacy workflow.yaml is auto-migrated to ID-only schema."""
    workflow_dir = legacy_workflow_project / "workflows" / "test_workflow"
    workflow_yaml_path = workflow_dir / "workflow.yaml"
    
    # Read original (legacy)
    original_data = yaml.safe_load(workflow_yaml_path.read_text())
    # Legacy format: step_id might be a name (not ULID)
    original_step_id = original_data["steps"][0].get("step_id") or original_data["steps"][0].get("id")
    assert original_step_id == "scf"  # Legacy name (not ULID)
    
    # Call list_workflows_data which should trigger migration
    QVService.list_workflows_data(legacy_workflow_project)
    
    # Re-read workflow.yaml - should now be migrated
    migrated_data = yaml.safe_load(workflow_yaml_path.read_text())
    
    # Should have step_id as ULID (not "scf")
    step_entry = migrated_data["steps"][0]
    assert "step_id" in step_entry
    assert len(step_entry["step_id"]) == 26  # ULID length
    assert step_entry["step_id"] != "scf"
    
    # Should NOT have step_file (ID-only model)
    assert "step_file" not in step_entry
    
    # Should NOT have legacy "id" field (or if present, it should be the ULID)
    if "id" in step_entry:
        assert step_entry["id"] == step_entry["step_id"]  # Should match step_id (ULID)

