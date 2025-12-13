import pytest

from quantumvitas.io import QEInput, QENamelist
from quantumvitas.calculation.input_runner import (
    ParameterOverride,
    _apply_parameter_overrides,
)


def _build_sample_pw_input() -> QEInput:
    return QEInput(
        namelists=[
            QENamelist("CONTROL", {"calculation": "scf"}),
            QENamelist("SYSTEM", {"ecutwfc": 20}),
        ]
    )


def test_apply_parameter_overrides_sets_value():
    qe_input = _build_sample_pw_input()
    _apply_parameter_overrides(
        qe_input, [ParameterOverride(name="ecutwfc", value=60)]
    )
    system = qe_input.get_namelist("system")
    assert system is not None
    assert system.parameters["ecutwfc"] == 60


def test_apply_parameter_overrides_requires_section_for_unknown_param():
    qe_input = _build_sample_pw_input()
    with pytest.raises(ValueError):
        _apply_parameter_overrides(
            qe_input, [ParameterOverride(name="not_a_param", value=1.0)]
        )


def test_apply_parameter_overrides_allows_manual_section_hint():
    qe_input = _build_sample_pw_input()
    _apply_parameter_overrides(
        qe_input,
        [ParameterOverride(name="new_param", value=1.5, section="SYSTEM")],
    )
    system = qe_input.get_namelist("system")
    assert system is not None
    assert system.parameters["new_param"] == 1.5

