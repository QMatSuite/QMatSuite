"""
Unit tests for legacy project migration.

Tests that the migration script correctly converts legacy projects
to the DAG + ULID model.
"""

import json
import yaml
from pathlib import Path

import pytest

from quantumvitas.core.exceptions import LegacyProjectError
from quantumvitas.core.models import load_workflow, load_project
from quantumvitas.legacy.migrate import migrate_legacy_project


def test_migrate_legacy_project_minimal(tmp_path):
    """Test migration of a minimal legacy project to DAG + ULID format."""
    project_root = tmp_path / "legacy_project"
    project_root.mkdir()
    
    # Create structures directory
    structures_dir = project_root / "structures"
    structures_dir.mkdir()
    
    # Create a minimal structure file with ULID
    from quantumvitas.core.resources import generate_resource_id
    structure_id = generate_resource_id()
    structure_file = structures_dir / "si.json"
    structure_data = {
        "meta": {
            "id": structure_id,
            "name": "Si",
            "slug": "si",
            "path": "structures/si.json",
            "kind": "structure",
        },
        "@module": "pymatgen.core.structure",
        "@class": "Structure",
        "lattice": {"matrix": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]},
        "sites": [],
    }
    structure_file.write_text(json.dumps(structure_data, indent=2))
    
    # Create workflows directory
    workflows_dir = project_root / "workflows"
    workflows_dir.mkdir()
    workflow_dir = workflows_dir / "si_flow"
    workflow_dir.mkdir()
    steps_dir = workflow_dir / "steps"
    steps_dir.mkdir()
    
    # Create legacy workflow.yaml with structure selector (no structure_id)
    workflow_ulid = generate_resource_id()
    legacy_workflow = {
        "meta": {
            "id": workflow_ulid,
            "name": "Si Flow",
            "slug": "si-flow",
            "path": "workflows/si_flow",
            "kind": "workflow",
        },
        "structure": "si",  # Legacy selector, no structure_id
        "steps": [
            {
                "id": "si_scf",  # Legacy id field, not step_id ULID
                "type": "scf",
                "step_file": "steps/si_scf.step.yaml",  # Legacy step_file
            },
        ],
    }
    workflow_yaml = workflow_dir / "workflow.yaml"
    workflow_yaml.write_text(yaml.safe_dump(legacy_workflow, sort_keys=False))
    
    # Create a minimal step file (legacy format)
    step_file = steps_dir / "si_scf.step.yaml"
    step_ulid = generate_resource_id()
    step_data = {
        "meta": {
            "id": step_ulid,
            "name": "si_scf",
            "slug": "si-scf",
            "path": "workflows/si_flow/steps/si_scf.step.yaml",
            "kind": "step",
        },
        "step_type": "scf",
    }
    step_file.write_text(yaml.safe_dump(step_data, sort_keys=False))
    
    # Create legacy project.qv.yml
    project_config = {
        "project": {
            "name": "Legacy Project",
            "meta": {
                "id": generate_resource_id(),
                "slug": "legacy-project",
            },
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
            },
        ],
        "workflows": [
            {
                "name": "Si Flow",
                "path": "workflows/si_flow",
            },
        ],
    }
    config_file = project_root / "project.qv.yml"
    config_file.write_text(yaml.safe_dump(project_config, sort_keys=False))
    
    # Before migration: loading should raise LegacyProjectError
    with pytest.raises(LegacyProjectError):
        load_workflow(workflow_dir, project_root)
    
    # Run migration
    migrate_legacy_project(project_root)
    
    # After migration: loading should succeed
    workflow_model = load_workflow(workflow_dir, project_root)
    
    # Verify migrated workflow has structure_id (ULID)
    assert workflow_model.structure_id is not None
    assert len(workflow_model.structure_id) == 26
    assert workflow_model.structure_id.startswith("01")
    assert workflow_model.structure_id == structure_id
    
    # Verify steps have step_id (ULID)
    assert len(workflow_model.steps) == 1
    step_entry = workflow_model.steps[0]
    assert step_entry.step_id is not None
    assert len(step_entry.step_id) == 26
    assert step_entry.step_id.startswith("01")
    # Should match the ULID from the step file
    assert step_entry.step_id == step_ulid
    
    # Verify workflow.yaml no longer has legacy fields
    workflow_data = yaml.safe_load(workflow_yaml.read_text())
    assert "structure_id" in workflow_data
    assert "structure" not in workflow_data
    assert "structure_name" not in workflow_data
    
    # Verify step entry no longer has legacy fields
    step_entry_dict = workflow_data["steps"][0]
    assert "step_id" in step_entry_dict
    assert "step_file" not in step_entry_dict
    assert "id" not in step_entry_dict
    
    # Verify step file exists
    migrated_step_file = steps_dir / "si-scf.step.yaml"  # May have been renamed to slug
    # Check if original or renamed file exists
    assert step_file.exists() or migrated_step_file.exists()
    
    # Verify project can be loaded without LegacyProjectError
    project = load_project(project_root)
    assert project is not None
    assert len(project.workflows) == 1
