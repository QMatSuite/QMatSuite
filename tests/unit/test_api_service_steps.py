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
        
        # Create a structure first (with meta)
        structures_dir = project_root / "structures"
        structures_dir.mkdir()
        structure_file = structures_dir / "si.json"
        structure_file.write_text("""{
  "__qv_meta__": {
    "id": "01TESTSTRUCTUREID123456789",
    "name": "Si",
    "slug": "si",
    "path": "structures/si.json",
    "kind": "structure"
  },
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
        
        # Create project.qv.yml with structure and workflow entries (ID-only)
        (project_root / "project.qv.yml").write_text("""name: Test Project
structures:
  - id: 01TESTSTRUCTUREID123456789
    file: structures/si.json
    meta:
      id: 01TESTSTRUCTUREID123456789
      name: Si
      slug: si
      path: structures/si.json
      kind: structure
workflows:
  - id: test-workflow-ulid
    path: workflows/test-workflow
    meta:
      id: test-workflow-ulid
      name: Test Workflow
      slug: test-workflow
      path: workflows/test-workflow
      kind: workflow
""")
        
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
structure_id: 01TESTSTRUCTUREID123456789
structure_name: Si
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
    # With ID-only model, step entry uses step_id (ULID) as canonical reference
    assert result["steps"][0].get("step_id") is not None, "Step entry should have step_id (ULID)"
    # Legacy id field may be None if step was created with step_id only
    # The step name "test-scf" is stored in the step spec meta, not in the workflow entry
    
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
    # DAG model: Step YAML should NOT contain structure_id (inherits from workflow)
    # Verify step YAML does not contain structure_id
    assert "structure_id" not in step_data, "Step YAML should not contain structure_id (DAG model)"
    # Structure is resolved via workflow.structure_id at runtime
    # The workflow should have structure_id set
    workflow_yaml = temp_project / "workflows" / "test-workflow" / "workflow.yaml"
    workflow_data = yaml.safe_load(workflow_yaml.read_text())
    assert workflow_data.get("structure_id") == "01TESTSTRUCTUREID123456789", "Workflow should reference structure via structure_id"
    
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
    # SYSTEM.occupations should NOT be present by default (only if explicitly set)
    assert "occupations" not in spec.parameters.get("SYSTEM", {}), \
        "occupations should not be in SYSTEM by default - only if explicitly set"
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

