import textwrap
from pathlib import Path

import pytest
import yaml

from quantumvitas.project.model import Project
from quantumvitas.workflow import (
    build_step_spec_from_qe_input,
    build_workflow_from_qe_inputs,
)
from quantumvitas.workflow.workflow import Workflow


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
    assert "structure:" in spec_text
    assert "K_POINTS" in spec_text  # cards captured
    assert "ATOMIC_SPECIES" in spec_text  # pseudo mapping stored in spec
    assert "ibrav" not in spec_text
    assert "celldm(1)" not in spec_text
    assert "nat" not in spec_text
    assert "ntyp" not in spec_text
    assert result.step_type == "scf"


def test_build_workflow_from_qe_inputs_and_load(tmp_path: Path):
    project_root = tmp_path / "project"
    workflow_dir = project_root / "workflows" / "si_flow"
    scf_file = _write_input(tmp_path, "si_scf.in", SIMPLE_SCF)
    nscf_file = _write_input(tmp_path, "si_nscf.in", SIMPLE_NSCF)

    result = build_workflow_from_qe_inputs(
        [scf_file, nscf_file],
        workflow_dir=workflow_dir,
        workflow_id="si_flow",
        structure_id="si",
        reference_structure_by="id",
        project_root=project_root,
    )

    assert result.workflow_file.exists()
    assert len(result.step_results) == 2

    # Create minimal project manifest referencing generated files
    structures_rel = result.structure_path.relative_to(project_root)
    project_config = {
        "project": {"name": "si_project"},
        "structures": [{"id": "si", "file": str(structures_rel)}],
        "workflows": [{"id": "si_flow", "path": "workflows/si_flow"}],
        "settings": {},
    }
    project_root.mkdir(parents=True, exist_ok=True)
    (project_root / "project.qv.yml").write_text(
        yaml.safe_dump(project_config, sort_keys=False)
    )

    project = Project.open(project_root)
    workflow = Workflow.from_yaml(workflow_dir, project)

    assert len(workflow.steps) == 2
    for step in workflow.steps:
        assert step.input_file.exists()

