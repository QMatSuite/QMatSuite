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
from quantumvitas.core.models import load_calculation, load_project
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
    
    # Create calculations directory
    calculations_dir = project_root / "calculations"
    calculations_dir.mkdir()
    calculation_dir = calculations_dir / "si_flow"
    calculation_dir.mkdir()
    steps_dir = calculation_dir / "steps"
    steps_dir.mkdir()
    
    # Create legacy calculation.yaml with structure selector (no structure_id)
    calculation_ulid = generate_resource_id()
    legacy_calculation = {
        "meta": {
            "id": calculation_ulid,
            "name": "Si Flow",
            "slug": "si-flow",
            "path": "calculations/si_flow",
            "kind": "calculation",
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
    calculation_yaml = calculation_dir / "calculation.yaml"
    calculation_yaml.write_text(yaml.safe_dump(legacy_calculation, sort_keys=False))
    
    # Create a minimal step file (legacy format)
    step_file = steps_dir / "si_scf.step.yaml"
    step_ulid = generate_resource_id()
    step_data = {
        "meta": {
            "id": step_ulid,
            "name": "si_scf",
            "slug": "si-scf",
            "path": "calculations/si_flow/steps/si_scf.step.yaml",
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
        "calculations": [
            {
                "name": "Si Flow",
                "path": "calculations/si_flow",
            },
        ],
    }
    config_file = project_root / "project.qv.yml"
    config_file.write_text(yaml.safe_dump(project_config, sort_keys=False))
    
    # Before migration: loading should raise LegacyProjectError
    with pytest.raises(LegacyProjectError):
        load_calculation(calculation_dir, project_root)
    
    # Run migration
    migrate_legacy_project(project_root)
    
    # After migration: loading should succeed
    calculation_model = load_calculation(calculation_dir, project_root)
    
    # Verify migrated calculation has structure_id (ULID)
    assert calculation_model.structure_id is not None
    assert len(calculation_model.structure_id) == 26
    assert calculation_model.structure_id.startswith("01")
    assert calculation_model.structure_id == structure_id
    
    # Verify steps have step_id (ULID)
    assert len(calculation_model.steps) == 1
    step_entry = calculation_model.steps[0]
    assert step_entry.step_id is not None
    assert len(step_entry.step_id) == 26
    assert step_entry.step_id.startswith("01")
    # Should match the ULID from the step file
    assert step_entry.step_id == step_ulid
    
    # Verify calculation.yaml no longer has legacy fields
    calculation_data = yaml.safe_load(calculation_yaml.read_text())
    assert "structure_id" in calculation_data
    assert "structure" not in calculation_data
    assert "structure_name" not in calculation_data
    
    # Verify step entry no longer has legacy fields
    step_entry_dict = calculation_data["steps"][0]
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
    assert len(project.calculations) == 1
