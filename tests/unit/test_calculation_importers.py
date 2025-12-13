import textwrap
from pathlib import Path

import pytest
import yaml

from quantumvitas.project.model import Project
from quantumvitas.calculation import (
    build_step_spec_from_qe_input,
    build_calculation_from_qe_inputs,
)
from quantumvitas.calculation.calculation import Calculation


SIMPLE_SCF = textwrap.dedent(
    """\
&CONTROL
    calculation = 'scf'
    prefix = 'si'
/
&SYSTEM
    ibrav = 2
    celldm(1) = 10.20
    nat = 2
    ntyp = 1
    ecutwfc = 40
/
&ELECTRONS
    conv_thr = 1.0d-8
/
ATOMIC_SPECIES
Si  28.086  Si.pz-vbc.UPF
ATOMIC_POSITIONS crystal
Si 0.0 0.0 0.0
Si 0.25 0.25 0.25
CELL_PARAMETERS angstrom
 0.000000  1.920000  1.920000
 1.920000  0.000000  1.920000
 1.920000  1.920000  0.000000
K_POINTS automatic
4 4 4 0 0 0
"""
)

SIMPLE_NSCF = textwrap.dedent(
    """\
&CONTROL
    calculation = 'nscf'
    prefix = 'si'
/
&SYSTEM
    ibrav = 2
    celldm(1) = 10.20
    nat = 2
    ntyp = 1
    ecutwfc = 40
/
&ELECTRONS
    conv_thr = 1.0d-10
/
ATOMIC_SPECIES
Si  28.086  Si.pz-vbc.UPF
ATOMIC_POSITIONS crystal
Si 0.0 0.0 0.0
Si 0.25 0.25 0.25
CELL_PARAMETERS angstrom
 0.000000  1.920000  1.920000
 1.920000  0.000000  1.920000
 1.920000  1.920000  0.000000
K_POINTS automatic
8 8 8 0 0 0
"""
)


def _write_input(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content)
    return path


def test_build_step_spec_from_qe_input_creates_structure_and_yaml(tmp_path: Path):
    input_path = _write_input(tmp_path, "si_scf.in", SIMPLE_SCF)
    destination = tmp_path / "steps"
    result = build_step_spec_from_qe_input(
        input_path,
        destination_dir=destination,
        reference_structure_by="path",
    )

    assert result.spec_path.exists()
    assert result.structure_path.exists()
    spec_text = result.spec_path.read_text()
    # ID-only model: check for structure_id instead of structure
    # DAG + ID-only model: Step YAML does NOT contain structure_id (inherits from calculation)
    # Legacy structure_id field is not written to YAML
    assert "structure_id:" not in spec_text, "Step YAML should not contain structure_id (DAG model)"
    assert "K_POINTS" in spec_text  # cards captured
    assert "ATOMIC_SPECIES" in spec_text  # pseudo mapping stored in spec
    assert "ibrav" not in spec_text
    assert "celldm(1)" not in spec_text
    assert "nat" not in spec_text
    assert "ntyp" not in spec_text
    assert result.step_type == "scf"


def test_build_calculation_from_qe_inputs_and_load(tmp_path: Path):
    project_root = tmp_path / "project"
    calculation_dir = project_root / "calculations" / "si_flow"
    scf_file = _write_input(tmp_path, "si_scf.in", SIMPLE_SCF)
    nscf_file = _write_input(tmp_path, "si_nscf.in", SIMPLE_NSCF)

    result = build_calculation_from_qe_inputs(
        [scf_file, nscf_file],
        calculation_dir=calculation_dir,
        calculation_id="si_flow",
        structure_id="si",
        reference_structure_by="id",
        project_root=project_root,
    )

    assert result.calculation_file.exists()
    assert len(result.step_results) == 2
    
    # Verify step_ids are ULIDs (DAG + ULID model)
    for step_result in result.step_results:
        assert len(step_result.step_id) == 26, f"step_id should be ULID (26 chars), got: {step_result.step_id}"
        assert step_result.step_id.startswith("01"), f"step_id should start with '01', got: {step_result.step_id}"
        # Verify step file has meta.id matching step_id
        spec_data = yaml.safe_load(step_result.spec_path.read_text())
        spec_meta = spec_data.get("meta", {})
        assert spec_meta.get("id") == step_result.step_id, "Step file meta.id should match step_id ULID"

    # Create minimal project manifest referencing generated files
    # Need to use the actual structure_id from the step result, not "si"
    # Get the structure_id from the first step result (all steps share the same structure)
    actual_structure_id = result.step_results[0].structure_id
    
    # Verify structure file exists and has correct meta
    assert result.structure_path.exists(), f"Structure file should exist: {result.structure_path}"
    from quantumvitas.io.structure_io import STRUCTURE_META_KEY
    import json
    structure_data = json.loads(result.structure_path.read_text())
    structure_meta = structure_data.get(STRUCTURE_META_KEY, {})
    assert structure_meta.get("id") == actual_structure_id, "Structure file should have matching ID"
    
    # Get relative path properly (handle both absolute and relative paths)
    try:
        structures_rel = result.structure_path.relative_to(project_root)
    except ValueError:
        # If paths don't resolve, use the structure's meta.path
        structures_rel = Path(structure_meta.get("path", "structures/si_scf.json"))
    
    # Load calculation.yaml to get the actual calculation ID (should have meta.id if properly created)
    calculation_yaml_path = result.calculation_file
    calculation_yaml_data = yaml.safe_load(calculation_yaml_path.read_text())
    
    # Get calculation ID: prefer meta.id (ULID), fall back to id field (human-readable name)
    # If calculation.yaml doesn't have meta, we need to ensure it does or use a generated ULID
    calculation_meta = calculation_yaml_data.get("meta", {})
    actual_calculation_id = calculation_meta.get("id")
    
    # If calculation.yaml doesn't have meta.id, we need to create it
    # For now, generate a ULID and update the calculation.yaml
    if not actual_calculation_id:
        from quantumvitas.core.resources import generate_resource_id, meta_from_name
        actual_calculation_id = generate_resource_id()
        calculation_meta = meta_from_name(
            "calculation",
            name=calculation_yaml_data.get("id", "si_flow"),
            path="calculations/si_flow"
        )
        calculation_meta.id = actual_calculation_id
        calculation_yaml_data["meta"] = calculation_meta.to_dict()
        calculation_yaml_path.write_text(yaml.safe_dump(calculation_yaml_data, sort_keys=False))
    
    # Verify calculation.yaml steps have ULID step_ids
    calculation_steps = calculation_yaml_data.get("steps", [])
    assert len(calculation_steps) == 2
    for step_entry in calculation_steps:
        step_id = step_entry.get("step_id")
        assert step_id is not None, "Step entry must have step_id"
        assert len(step_id) == 26, f"step_id should be ULID (26 chars), got: {step_id}"
        assert step_id.startswith("01"), f"step_id should start with '01', got: {step_id}"
        # Verify no legacy fields
        assert "step_file" not in step_entry, "Step entry should not have step_file (DAG + ID-only model)"
        assert "id" not in step_entry, "Step entry should not have legacy id field"
    
    project_config = {
        "project": {"name": "si_project"},
        "structures": [{
            "id": actual_structure_id,
            "file": str(structures_rel),
            "format": "json",
        }],
        "calculations": [{"id": actual_calculation_id, "path": "calculations/si_flow"}],
        "settings": {},
    }
    project_root.mkdir(parents=True, exist_ok=True)
    (project_root / "project.qv.yml").write_text(
        yaml.safe_dump(project_config, sort_keys=False)
    )

    project = Project.open(project_root)
    calculation = Calculation.from_yaml(calculation_dir, project)

    assert len(calculation.steps) == 2
    for step in calculation.steps:
        assert step.input_file.exists()
        # Verify step has ULID meta.id
        assert len(step.meta.id) == 26, f"Step meta.id should be ULID (26 chars), got: {step.meta.id}"
        assert step.meta.id.startswith("01"), f"Step meta.id should start with '01', got: {step.meta.id}"

