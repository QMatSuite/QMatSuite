import pytest
import warnings

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
    # Qualified override with unknown parameter: should write with warning
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # Ignore warning for unknown parameter
        _apply_parameter_overrides(
            qe_input,
            [ParameterOverride(name="new_param", value=1.5, section="SYSTEM")],
        )
    system = qe_input.get_namelist("system")
    assert system is not None
    assert system.parameters["new_param"] == 1.5


# New tests for unqualified/qualified parameter rules

def test_unqualified_parameter_writes_to_canonical_section():
    """
    Test: ecutwfc=50 writes to SYSTEM.ecutwfc even if ELECTRONS.ecutwfc exists.
    """
    qe_input = QEInput(
        namelists=[
            QENamelist("CONTROL", {"calculation": "scf"}),
            QENamelist("SYSTEM", {}),
            QENamelist("ELECTRONS", {"ecutwfc": 40}),  # Wrong section, but preserved
        ]
    )
    
    # Unqualified override: should write to canonical section (SYSTEM)
    _apply_parameter_overrides(
        qe_input, [ParameterOverride(name="ecutwfc", value=50, section=None)]
    )
    
    system = qe_input.get_namelist("system")
    electrons = qe_input.get_namelist("electrons")
    
    assert system is not None
    assert system.parameters["ecutwfc"] == 50  # Written to canonical section
    
    assert electrons is not None
    assert electrons.parameters["ecutwfc"] == 40  # Original value preserved in wrong section


def test_qualified_parameter_overwrites_specified_section():
    """
    Test: ELECTRONS.ecutwfc=60 overwrites ELECTRONS.ecutwfc.
    """
    qe_input = QEInput(
        namelists=[
            QENamelist("CONTROL", {"calculation": "scf"}),
            QENamelist("SYSTEM", {"ecutwfc": 50}),
            QENamelist("ELECTRONS", {"ecutwfc": 40}),
        ]
    )
    
    # Qualified override: should write to specified section
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # Ignore mismatch warning
        _apply_parameter_overrides(
            qe_input, [ParameterOverride(name="ecutwfc", value=60, section="ELECTRONS")]
        )
    
    system = qe_input.get_namelist("system")
    electrons = qe_input.get_namelist("electrons")
    
    assert system is not None
    assert system.parameters["ecutwfc"] == 50  # Unchanged
    
    assert electrons is not None
    assert electrons.parameters["ecutwfc"] == 60  # Overwritten in specified section


def test_unqualified_unknown_parameter_raises_error():
    """
    Test: fakeparameter=10 (unqualified) raises ValueError with helpful message.
    """
    qe_input = _build_sample_pw_input()
    
    with pytest.raises(ValueError, match="not defined for module.*Provide the section explicitly"):
        _apply_parameter_overrides(
            qe_input, [ParameterOverride(name="fakeparameter", value=10, section=None)]
        )


def test_qualified_unknown_parameter_writes_with_warning():
    """
    Test: SYSTEM.fakeparameter=10 writes successfully but emits warning.
    """
    qe_input = _build_sample_pw_input()
    
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        _apply_parameter_overrides(
            qe_input, [ParameterOverride(name="fakeparameter", value=10, section="SYSTEM")]
        )
        
        # Should emit warning about unknown parameter
        assert len(w) > 0
        assert any("not defined in QE schema" in str(warning.message) for warning in w)
    
    system = qe_input.get_namelist("system")
    assert system is not None
    assert system.parameters["fakeparameter"] == 10  # Written successfully

