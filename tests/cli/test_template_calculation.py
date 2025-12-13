"""
Test that calculation created from template can be run successfully.

This test uses a snapshot-based project which contains a complete Si DOS calculation
with scf, nscf, and dos steps.
"""

import pytest
from pathlib import Path
import yaml
import shutil

from typer.testing import CliRunner

from quantumvitas.cli.main import app

runner = CliRunner()


@pytest.fixture
def template_project(tmp_path, project_root_path):
    """Create a project from example project data."""
    # Use project1 example from tests/data/project_examples/
    example_project = project_root_path / "tests" / "data" / "project_examples" / "project1"
    project_dir = tmp_path / "test_project"
    
    # Copy the example project
    shutil.copytree(example_project, project_dir)
    
    assert project_dir.exists()
    assert (project_dir / "project.qv.yml").exists()
    
    return project_dir


def test_template_project_structure(template_project):
    """Test that project template creates correct structure."""
    project_dir = template_project
    
    # Check project.qv.yml exists
    assert (project_dir / "project.qv.yml").exists()
    
    # Check structures directory
    structures_dir = project_dir / "structures"
    assert structures_dir.exists()
    
    # Check calculations directory  
    calculations_dir = project_dir / "calculations"
    assert calculations_dir.exists()
    
    # Check that si-dos calculation exists
    si_dos_dir = calculations_dir / "si-dos"
    assert si_dos_dir.exists()
    assert (si_dos_dir / "calculation.yaml").exists()
    
    # Check step files
    steps_dir = si_dos_dir / "steps"
    assert steps_dir.exists()
    assert (steps_dir / "scf.step.yaml").exists()
    assert (steps_dir / "nscf.step.yaml").exists()
    assert (steps_dir / "dos.step.yaml").exists()


def test_template_calculation_ulids_consistent(template_project):
    """Test that calculation ULID in project.qv.yml matches step parent_calculation_id."""
    project_dir = template_project
    
    # Load project config
    config = yaml.safe_load((project_dir / "project.qv.yml").read_text())
    
    # Find si-dos calculation using centralized selector extraction
    from quantumvitas.core.selectors import extract_calculation_selector_from_entry
    
    calculation_entry = None
    for wf in config.get("calculations", []):
        # Check by path (most reliable in ID-only model)
        path = wf.get("path") or (wf.get("meta") or {}).get("path", "")
        if path.endswith("si-dos"):
            calculation_entry = wf
            break
        # Also check by slug/name from calculation.yaml if available
        calculation_selector = extract_calculation_selector_from_entry(wf)
        if calculation_selector and "si-dos" in str(calculation_selector).lower():
            # Resolve to check if it's actually si-dos
            try:
                from quantumvitas.core.resolution import build_resource_index, require_calculation
                index = build_resource_index(project_dir)
                resolved = require_calculation(project_dir, calculation_selector, index=index)
                if resolved.meta.slug == "si-dos" or resolved.meta.name == "si-dos":
                    calculation_entry = wf
                    break
            except Exception:
                pass
    
    # Fallback: check calculation.yaml directly
    if calculation_entry is None:
        calculation_yaml_path = project_dir / "calculations" / "si-dos" / "calculation.yaml"
        if calculation_yaml_path.exists():
            wf_data = yaml.safe_load(calculation_yaml_path.read_text())
            wf_id = (wf_data.get("meta") or {}).get("id")
            if wf_id:
                # Find entry by ID
                for wf in config.get("calculations", []):
                    entry_id = extract_calculation_selector_from_entry(wf)
                    if entry_id == wf_id:
                        calculation_entry = wf
                        break
    
    assert calculation_entry is not None, "si-dos calculation not found in project.qv.yml"
    
    # In ID-only model, calculation entry might have calculation_id (ULID) directly or in meta.id
    calculation_ulid = (
        calculation_entry.get("calculation_id") or
        calculation_entry.get("id") or
        (calculation_entry.get("meta") or {}).get("id")
    )
    assert calculation_ulid, "Calculation should have a ULID (calculation_id, id, or meta.id)"
    
    # DAG model: Step YAML should NOT contain parent_calculation_id
    # Verify step files do not contain parent_calculation_id
    steps_dir = project_dir / "calculations" / "si-dos" / "steps"
    for step_file in steps_dir.glob("*.step.yaml"):
        step_data = yaml.safe_load(step_file.read_text())
        # Step YAML should not contain parent_calculation_id (DAG model)
        assert "parent_calculation_id" not in step_data, (
            f"Step {step_file.name} should not contain parent_calculation_id (DAG model)"
        )


def test_template_structure_copied(template_project):
    """Test that structure referenced by calculation is copied."""
    project_dir = template_project
    
    # Load calculation
    calculation_yaml = project_dir / "calculations" / "si-dos" / "calculation.yaml"
    calculation_data = yaml.safe_load(calculation_yaml.read_text())
    
    # ID-only model: check for structure_id instead of structure
    structure_id = calculation_data.get("structure_id")
    assert structure_id, "Calculation should reference a structure via structure_id"
    
    # Check structure file exists by resolving via project
    from quantumvitas.project.model import Project
    project = Project.open(project_dir)
    structure_ref = project.get_structure(structure_id)
    assert structure_ref.absolute_path.exists(), f"Structure file {structure_ref.absolute_path} should exist"


@pytest.mark.qe_cli
def test_template_calculation_runs(template_project):
    """Test that calculation from template can be executed with QE."""
    project_dir = template_project
    
    # Run the calculation
    result = runner.invoke(
        app,
        ["run", "calculation", "si-dos", "--project", str(project_dir)],
        catch_exceptions=False
    )
    
    # Check result
    assert "Calculation si-dos status: StepStatus.SUCCESS" in result.output, (
        f"Calculation should succeed. Output:\n{result.output}"
    )


def test_init_calculation_from_template_with_custom_structure(tmp_path):
    """Test creating calculation from template with custom structure."""
    project_dir = tmp_path / "proj"
    
    # First create empty project
    result = runner.invoke(
        app,
        ["init", "project", "--path", str(project_dir)],
        catch_exceptions=False
    )
    assert result.exit_code == 0
    
    # Import a structure
    from pymatgen.core import Structure, Lattice
    import json
    
    struct = Structure(Lattice.cubic(5.0), ["Si", "Si"], [[0, 0, 0], [0.5, 0.5, 0.5]])
    structures_dir = project_dir / "structures"
    structures_dir.mkdir(exist_ok=True)
    
    # Generate proper ULID for structure
    from quantumvitas.core.resources import generate_resource_id
    structure_ulid = generate_resource_id()
    
    struct_file = structures_dir / "custom_si.json"
    with open(struct_file, "w") as f:
        json.dump({
            "structure": struct.as_dict(),
            "__qv_meta__": {
                "id": structure_ulid,
                "name": "custom_si",
                "slug": "custom_si",
                "path": "structures/custom_si.json",
                "kind": "structure"
            }
        }, f)
    
    # Register structure in project
    config = yaml.safe_load((project_dir / "project.qv.yml").read_text())
    config.setdefault("structures", []).append({
        "structure_id": structure_ulid,  # ID-only reference (ULID)
    })
    with open(project_dir / "project.qv.yml", "w") as f:
        yaml.safe_dump(config, f)
    
    # Create calculation from template using the custom structure
    result = runner.invoke(
        app,
        ["init", "calculation", "my-calculation", "--template", "si-dos", 
         "--structure", "custom_si", "--project", str(project_dir)],
        catch_exceptions=False
    )
    assert result.exit_code == 0, f"Failed: {result.output}"
    
    # Check calculation uses custom structure
    calculation_yaml = project_dir / "calculations" / "my-calculation" / "calculation.yaml"
    calculation_data = yaml.safe_load(calculation_yaml.read_text())
    # ID-only model: calculation should reference structure via structure_id (ULID)
    structure_id = calculation_data.get("structure_id")
    assert structure_id is not None, "Calculation should reference structure via structure_id (ULID)"
    # Verify structure_id is a ULID (26 chars), not a human-readable name
    assert len(structure_id) == 26, "structure_id should be a ULID, not a human-readable name"
    # Verify it resolves to the custom structure
    from quantumvitas.core.resolution import resolve_structure
    resolved_structure = resolve_structure(project_dir, structure_id)
    assert resolved_structure.meta.slug == "custom_si", "Calculation should reference custom_si structure"
    
    # DAG model: Step YAML should NOT contain structure_id (inherits from calculation)
    # Verify step files do not contain structure_id
    steps_dir = project_dir / "calculations" / "my-calculation" / "steps"
    for step_file in steps_dir.glob("*.step.yaml"):
        step_data = yaml.safe_load(step_file.read_text())
        assert "structure_id" not in step_data, (
            f"Step {step_file.name} should not contain structure_id (DAG model)"
        )
        assert "structure" not in step_data, (
            f"Step {step_file.name} should not contain structure selector (DAG model)"
        )

