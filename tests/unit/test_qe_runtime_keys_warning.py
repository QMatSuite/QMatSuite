"""
Unit tests for runtime CONTROL keys warning detection.

Tests that warnings are emitted when steps have prefix/outdir/pseudo_dir
in CONTROL section (pure keyword matching, no engine detection).
"""

import tempfile
from pathlib import Path

import pytest
import yaml

from qmatsuite.api import get_service
from qmatsuite.calculation.structure_steps import (
    detect_runtime_control_keys,
    StructureStepSpec,
)
from qmatsuite.core.resources import generate_resource_id, meta_from_name


@pytest.fixture
def temp_project_with_step():
    """Create a temporary project with a structure, calculation, and step."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir) / "test_project"
        project_root.mkdir()
        
        # Create a structure
        structures_dir = project_root / "structures"
        structures_dir.mkdir()
        structure_ulid = generate_resource_id()
        structure_file = structures_dir / "si.json"
        structure_file.write_text("""{
  "__qms_meta__": {
    "ulid": "01TESTSTRUCTUREID123456789",
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
        
        # Create calculation
        calculation_id = generate_resource_id()
        calc_dir = project_root / "calculations" / "wf"
        calc_dir.mkdir(parents=True)
        steps_dir = calc_dir / "steps"
        steps_dir.mkdir(parents=True)
        
        (project_root / "project.qms.yml").write_text(f"""name: Test Project
structures:
  - ulid: {structure_ulid}
    file: structures/si.json
    slug: si
    name: Si
    kind: structure
calculations:
  - ulid: {calculation_id}
    path: calculations/wf
    slug: wf
    name: wf
    kind: calculation
""")
        
        (calc_dir / "calculation.yaml").write_text(f"""meta:
  ulid: {calculation_id}
  id: {calculation_id}
  name: wf
  slug: wf
  path: calculations/wf
  kind: calculation
structure_ulid: {structure_ulid}
steps: []
""")
        
        # Create a step
        step_id = generate_resource_id()
        step_file = steps_dir / "scf.step.yaml"
        step_meta = meta_from_name("step", name="scf", path="steps/scf.step.yaml")
        step_meta.ulid = step_id  # ResourceMeta uses .ulid
        step_spec = StructureStepSpec(
            meta=step_meta,
            structure="",
            step_type_spec="qe_scf",
            parameters={},
        )
        step_file.write_text(yaml.safe_dump(step_spec.to_dict(), sort_keys=False))
        
        # Update calculation.yaml to reference step
        calc_data = yaml.safe_load((calc_dir / "calculation.yaml").read_text())
        calc_data["steps"] = [{"step_ulid": step_id, "step_type_spec": "qe_scf"}]
        (calc_dir / "calculation.yaml").write_text(yaml.safe_dump(calc_data, sort_keys=False))
        
        yield project_root, calculation_id, step_id, step_file


def test_detect_runtime_control_keys():
    """Test that detect_runtime_control_keys correctly identifies runtime keys."""
    # Test with prefix
    params1 = {"CONTROL": {"prefix": "test", "calculation": "scf"}}
    assert "prefix" in detect_runtime_control_keys(params1)
    
    # Test with outdir
    params2 = {"CONTROL": {"outdir": "./outdir", "calculation": "scf"}}
    assert "outdir" in detect_runtime_control_keys(params2)
    
    # Test with pseudo_dir
    params3 = {"CONTROL": {"pseudo_dir": "/path/to/pseudo", "calculation": "scf"}}
    assert "pseudo_dir" in detect_runtime_control_keys(params3)
    
    # Test with multiple keys
    params4 = {"CONTROL": {"prefix": "test", "outdir": "./outdir", "pseudo_dir": "/path", "calculation": "scf"}}
    found = detect_runtime_control_keys(params4)
    assert "prefix" in found
    assert "outdir" in found
    assert "pseudo_dir" in found
    
    # Test with no runtime keys
    params5 = {"CONTROL": {"calculation": "scf", "restart_mode": "from_scratch"}}
    assert len(detect_runtime_control_keys(params5)) == 0
    
    # Test case-insensitive
    params6 = {"control": {"PREFIX": "test"}}  # lowercase section, uppercase key
    assert "prefix" in detect_runtime_control_keys(params6)
    
    # Test with no CONTROL section
    params7 = {"SYSTEM": {"ecutwfc": 50}}
    assert len(detect_runtime_control_keys(params7)) == 0


def test_update_step_params_preserves_runtime_keys(temp_project_with_step):
    """Test that update_step_params preserves runtime CONTROL keys (doesn't strip them)."""
    project_root, calculation_id, step_id, step_file = temp_project_with_step

    # Update step with outdir (runtime key)
    svc = get_service(project_root)
    svc.calculation.update_step_params(
        calc_selector=calculation_id,
        step_selector=step_id,
        params={"CONTROL": {"outdir": "./custom_outdir"}},
    )

    # Verify step.yaml still contains the key (no stripping)
    # Runtime keys are preserved - warnings are detected at kernel level (not API)
    # Note: CONTROL is a top-level key in step YAML, not nested under "parameters"
    step_data = yaml.safe_load(step_file.read_text())
    assert step_data["CONTROL"]["outdir"] == "./custom_outdir"

