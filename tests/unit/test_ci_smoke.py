"""
Lightweight smoke tests that run with the rest of the suite.
"""

import pytest

from quantumvitas.io import QEInputParser, QEInputGenerator

pytestmark = pytest.mark.unit


def test_imports():
    """Ensure the public IO helpers can be imported."""
    assert QEInputParser is not None
    assert QEInputGenerator is not None


def test_basic_roundtrip():
    """Parse a tiny QE input string and ensure we can regenerate it."""
    content = """&control
    calculation = 'scf'
    prefix = 'test'
/
&system
    nat = 1
    ecutwfc = 30.0
/
"""
    qe_input = QEInputParser.parse_string(content)
    assert qe_input.get_namelist("control").get("calculation") == "scf"
    regenerated = QEInputGenerator.generate(qe_input)
    assert "calculation = 'scf'" in regenerated

