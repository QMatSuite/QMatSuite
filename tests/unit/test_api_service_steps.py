"""
Unit tests for QVService step-related methods.

Tests that verify step creation through the API layer works correctly,
especially ensuring that executable is not part of the step spec.
"""

import tempfile
from pathlib import Path

import pytest
import yaml

from quantumvitas.api import QVService
from quantumvitas.workflow.structure_steps import StructureStepSpec


@pytest.fixture
def temp_project():
    """Create a temporary project with a structure and workflow."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir) / "test_project"
        project_root.mkdir()
        
        # Create project.qv.yml with workflow entry
        (project_root / "project.qv.yml").write_text("""name: Test Project
workflows:
  - meta:
      id: test-workflow-ulid
      name: Test Workflow
      slug: test-workflow
      path: workflows/test-workflow
      kind: workflow
    workflow:
      structure: structures/si.json
""")
        
        # Create a structure
        structures_dir = project_root / "structures"
        structures_dir.mkdir()
        structure_file = structures_dir / "si.json"
        structure_file.write_text("""{
  "@module": "Structure",
  "@class": "Structure",
  "lattice": {
    "matrix": [[3.84, 0.0, 0.0], [0.0, 3.84, 0.0], [0.0, 0.0, 3.84]]
  },
  "sites": [
    {"species": [{"element": "Si", "occu": 1}], "abc": [0.0, 0.0, 0.0]},
    {"species": [{"element": "Si", "occu": 1}], "abc": [0.25, 0.25, 0.25]}
  ]
}""")
        
        # Create a workflow
        workflows_dir = project_root / "workflows"
        workflows_dir.mkdir()
        workflow_dir = workflows_dir / "test-workflow"
        workflow_dir.mkdir()
        workflow_yaml = workflow_dir / "workflow.yaml"
        workflow_yaml.write_text("""meta:
  id: test-workflow-ulid
  name: Test Workflow
  slug: test-workflow
  path: workflows/test-workflow
  kind: workflow
workflow:
  structure: structures/si.json
steps: []
""")
        
        yield project_root


def test_add_step_to_workflow_creates_valid_spec(temp_project):
    """Test that add_step_to_workflow creates a valid step spec without executable."""
    # Add a step (use name as selector)
    result = QVService.add_step_to_workflow(
        project_root=temp_project,
        workflow_selector="Test Workflow",  # Use name
        step_type="scf",
        step_name="test-scf",
    )
    
    # Verify result
    assert result is not None
    assert "steps" in result
    assert len(result["steps"]) == 1
    assert result["steps"][0]["type"] == "scf"
    assert result["steps"][0]["id"] == "test-scf"
    
    # Load the step spec file
    step_file = temp_project / "workflows" / "test-workflow" / "steps" / "test-scf.step.yaml"
    assert step_file.exists()
    
    # Parse the YAML
    step_data = yaml.safe_load(step_file.read_text())
    
    # Verify no executable field
    assert "executable" not in step_data
    
    # Verify it can be loaded as StructureStepSpec
    spec = StructureStepSpec.from_dict(step_data, source_path=step_file)
    assert spec.step_type == "scf"
    assert spec.structure == "structures/si.json"
    
    # Verify defaults are present (from-scratch mode uses defaults)
    assert "CONTROL" in spec.parameters
    assert "outdir" in spec.parameters["CONTROL"]
    assert "restart_mode" in spec.parameters["CONTROL"]
    assert "ELECTRONS" in spec.parameters
    assert "conv_thr" in spec.parameters["ELECTRONS"]


def test_add_step_to_workflow_with_defaults(temp_project):
    """Test that add_step_to_workflow applies default parameters."""
    # Add an nscf step
    result = QVService.add_step_to_workflow(
        project_root=temp_project,
        workflow_selector="Test Workflow",  # Use name
        step_type="nscf",
    )
    
    # Load the step spec
    step_file = temp_project / "workflows" / "test-workflow" / "steps" / "nscf.step.yaml"
    assert step_file.exists()
    
    spec = StructureStepSpec.from_dict(
        yaml.safe_load(step_file.read_text()),
        source_path=step_file
    )
    
    # Verify nscf defaults are present
    assert spec.parameters["CONTROL"]["calculation"] == "nscf"
    assert spec.parameters["SYSTEM"]["occupations"] == "tetrahedra"
    assert "K_POINTS" in spec.cards


def test_add_step_to_workflow_no_executable_in_spec(temp_project):
    """Explicitly verify that executable is never in the step spec."""
    # Add multiple step types
    for step_type in ["scf", "dos", "bands"]:
        QVService.add_step_to_workflow(
            project_root=temp_project,
            workflow_selector="Test Workflow",  # Use name
            step_type=step_type,
            step_name=f"test-{step_type}",
        )
    
    # Check all step files
    steps_dir = temp_project / "workflows" / "test-workflow" / "steps"
    for step_file in steps_dir.glob("*.step.yaml"):
        step_data = yaml.safe_load(step_file.read_text())
        assert "executable" not in step_data, f"Step {step_file.name} contains executable field"
        
        # Also verify StructureStepSpec doesn't have it
        spec = StructureStepSpec.from_dict(step_data, source_path=step_file)
        assert not hasattr(spec, "executable"), f"StructureStepSpec from {step_file.name} has executable attribute"

