from pathlib import Path

import pytest
from pymatgen.core import Lattice, Structure

from quantumvitas.calculation.structure_steps import (
    StructureStepSpec,
    generate_qe_input_from_spec,
    generate_qe_input_from_structure,
)
from quantumvitas.calculation.input_runner import ParameterOverride


@pytest.fixture
def sample_structure():
    return Structure(Lattice.cubic(5.43), ["Si", "Si"], [[0, 0, 0], [0.25, 0.25, 0.25]])


def test_structure_step_spec_from_dict():
    data = {
        "structure": "si",
        "step_type": "nscf",
        "parameters": {
            "SYSTEM": {"ecutwfc": 60},
            "ELECTRONS": {"conv_thr": 1e-8},
        },
        "input_name": "si_nscf.pw.in",
    }
    spec = StructureStepSpec.from_dict(data)
    assert spec.structure == "si"
    assert spec.step_type == "nscf"
    assert spec.parameters["SYSTEM"]["ecutwfc"] == 60
    assert spec.input_name == "si_nscf.pw.in"


def test_generate_qe_input_from_structure_applies_step_type(sample_structure):
    overrides = [ParameterOverride(name="ecutwfc", value=60, section="SYSTEM")]
    qe_input = generate_qe_input_from_structure(
        structure=sample_structure,
        step_type="nscf",
        parameter_overrides=overrides,
    )
    control = qe_input.get_namelist("CONTROL")
    assert control.get("calculation") == "nscf"
    system = qe_input.get_namelist("SYSTEM")
    assert system.get("ecutwfc") == 60


def test_generate_qe_input_from_spec(sample_structure, tmp_path):
    spec_data = {
        "structure": "si",
        "step_type": "scf",
        "parameters": {
            "SYSTEM": {"ecutwfc": 50},
            "CONTROL": {"prefix": "si"},
        },
        "species_overrides": {"Si": {"pseudopot": "Si.upf"}},  # Required for standalone mode
    }
    spec = StructureStepSpec.from_dict(spec_data)
    qe_input, overrides = generate_qe_input_from_spec(sample_structure, spec)
    assert len(overrides) == 2
    control = qe_input.get_namelist("CONTROL")
    assert control.get("calculation") == "scf"
    assert control.get("prefix") == "si"
    system = qe_input.get_namelist("SYSTEM")
    assert system.get("ecutwfc") == 50

