"""
Unit tests for QVService step-related methods.

Tests that verify step creation through the API layer works correctly,
especially ensuring that executable is not part of the step spec.
"""

import tempfile
from pathlib import Path

import pytest
import yaml

from quantumvitas.api import QVService, get_service
from quantumvitas.calculation.structure_steps import StructureStepSpec


@pytest.fixture
def temp_project():
    """Create a temporary project with a structure and calculation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir) / "test_project"
        project_root.mkdir()

        # Create a structure first (with meta)
        structures_dir = project_root / "structures"
        structures_dir.mkdir()
        structure_file = structures_dir / "si.json"
        structure_file.write_text("""{
  "__qv_meta__": {
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

        # Create project.qv.yml with structure and calculation entries (ID-only)
        (project_root / "project.qv.yml").write_text("""name: Test Project
structures:
  - ulid: 01TESTSTRUCTUREID123456789
    file: structures/si.json
    meta:
      ulid: 01TESTSTRUCTUREID123456789
      name: Si
      slug: si
      path: structures/si.json
      kind: structure
calculations:
  - calculation_id: test-calculation-ulid
    path: calculations/test-calculation
    meta:
      ulid: test-calculation-ulid
      name: Test Calculation
      slug: test-calculation
      path: calculations/test-calculation
      kind: calculation
""")

        # Create a calculation
        calculations_dir = project_root / "calculations"
        calculations_dir.mkdir()
        calculation_dir = calculations_dir / "test-calculation"
        calculation_dir.mkdir()
        calculation_yaml = calculation_dir / "calculation.yaml"
        calculation_yaml.write_text("""meta:
  ulid: test-calculation-ulid
  name: Test Calculation
  slug: test-calculation
  path: calculations/test-calculation
  kind: calculation
structure_ulid: 01TESTSTRUCTUREID123456789
structure_name: Si
engine_family: qe
steps: []
""")

        yield project_root


def test_add_step_to_calculation_creates_valid_spec(temp_project):
    """Test that add_step creates a valid step spec without executable."""
    svc = get_service(temp_project)

    # Add a step (use name as selector)
    result = svc.calculation.add_step(
        calc_selector="Test Calculation",  # Use name
        step_type_gen="scf",
        name="test-scf",
    )

    # Verify result is a StepDTO
    assert result is not None
    assert result.step_ulid is not None, "StepDTO should have step_ulid (ULID)"
    # Step type should be SPEC ("qe_scf")
    assert result.step_type_spec == "qe_scf", f"Expected step_type_spec to be 'qe_scf', got '{result.step_type_spec}'"
    assert result.step_type_gen == "scf", f"Expected step_type_gen to be 'scf', got '{result.step_type_gen}'"

    # Load the step spec file
    step_file = temp_project / "calculations" / "test-calculation" / "steps" / "test-scf.step.yaml"
    assert step_file.exists()

    # Parse the YAML
    step_data = yaml.safe_load(step_file.read_text())

    # Verify no executable field
    assert "executable" not in step_data

    # Verify it can be loaded as StructureStepSpec
    spec = StructureStepSpec.from_dict(step_data, source_path=step_file)
    assert spec.step_type_spec == "qe_scf", f"Expected step_type_spec to be 'qe_scf', got '{spec.step_type_spec}'"
    # DAG model: Step YAML should NOT contain structure_ulid (inherits from calculation)
    # Verify step YAML does not contain structure_ulid
    assert "structure_ulid" not in step_data, "Step YAML should not contain structure_ulid (DAG model)"
    # Structure is resolved via calculation.structure_ulid at runtime
    # The calculation should have structure_ulid set
    calculation_yaml = temp_project / "calculations" / "test-calculation" / "calculation.yaml"
    calculation_data = yaml.safe_load(calculation_yaml.read_text())
    assert calculation_data.get("structure_ulid") == "01TESTSTRUCTUREID123456789", "Calculation should reference structure via structure_ulid"

    # Verify defaults are present (from-scratch mode uses defaults)
    assert "CONTROL" in spec.parameters
    assert "outdir" in spec.parameters["CONTROL"]
    assert "restart_mode" in spec.parameters["CONTROL"]
    assert "ELECTRONS" in spec.parameters
    assert "conv_thr" in spec.parameters["ELECTRONS"]


def test_add_step_to_calculation_with_defaults(temp_project):
    """Test that add_step applies default parameters."""
    svc = get_service(temp_project)

    # Add an nscf step
    result = svc.calculation.add_step(
        calc_selector="Test Calculation",  # Use name
        step_type_gen="nscf",
    )

    # Load the step spec
    step_file = temp_project / "calculations" / "test-calculation" / "steps" / "nscf.step.yaml"
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


def test_add_step_to_calculation_no_executable_in_spec(temp_project):
    """Explicitly verify that executable is never in the step spec."""
    svc = get_service(temp_project)

    # Add multiple step types
    for step_type in ["scf", "dos", "bands"]:
        svc.calculation.add_step(
            calc_selector="Test Calculation",  # Use name
            step_type_gen=step_type,
            name=f"test-{step_type}",
        )

    # Check all step files
    steps_dir = temp_project / "calculations" / "test-calculation" / "steps"
    for step_file in steps_dir.glob("*.step.yaml"):
        step_data = yaml.safe_load(step_file.read_text())
        assert "executable" not in step_data, f"Step {step_file.name} contains executable field"

        # Also verify StructureStepSpec doesn't have it
        spec = StructureStepSpec.from_dict(step_data, source_path=step_file)
        assert not hasattr(spec, "executable"), f"StructureStepSpec from {step_file.name} has executable attribute"


def test_configure_step_species_overrides(temp_project):
    """Test that update_step_params handles species_overrides correctly using apply_patch."""
    from quantumvitas.core.yamldoc import StepDoc

    svc = get_service(temp_project)

    # Add a step first
    svc.calculation.add_step(
        calc_selector="Test Calculation",
        step_type_gen="scf",
        name="test-scf",
    )

    # Configure step with species_overrides (dict value)
    svc.calculation.update_step_params(
        calc_selector="Test Calculation",
        step_selector="test-scf",
        params={
            "species_overrides": {
                "Si": {"pseudopot": "Si.UPF"},
            },
        },
    )

    # Load step and verify species_overrides was set correctly
    step_file = temp_project / "calculations" / "test-calculation" / "steps" / "test-scf.step.yaml"
    step_doc = StepDoc.load(step_file)

    species_overrides = step_doc.export_copy(["species_overrides"])
    assert species_overrides is not None
    assert "Si" in species_overrides
    assert species_overrides["Si"]["pseudopot"] == "Si.UPF"
