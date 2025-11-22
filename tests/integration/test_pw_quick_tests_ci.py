"""
CI-friendly quick tests for PW module.

This module provides tests that work in CI environments where QE may not be available.
Tests will gracefully skip if QE is not found.
"""

import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from quantumvitas.core.engines.qe_input import QEInputParser, QEInputGenerator

# Mark as quick test (but not requires_qe, so it runs in CI)
pytestmark = pytest.mark.quick


class TestPWQuickParsing:
    """Quick parsing tests that don't require QE installation."""
    
    def test_parse_basic_scf(self):
        """Test parsing a basic SCF input."""
        content = """&control
    calculation = 'scf'
    prefix = 'test'
/
&system
    ibrav = 0
    nat = 2
    ntyp = 1
    ecutwfc = 30.0
/
ATOMIC_SPECIES
Si 28.085 Si.pbe-n-rrkjus.UPF
ATOMIC_POSITIONS alat
Si 0.0 0.0 0.0
Si 0.25 0.25 0.25
K_POINTS gamma
"""
        qe_input = QEInputParser.parse_string(content)
        assert qe_input.get_namelist("control") is not None
        assert qe_input.get_namelist("system") is not None
        
        control = qe_input.get_namelist("control")
        assert control.get("calculation") == "scf"
        assert control.get("prefix") == "test"
    
    def test_generate_basic_input(self):
        """Test generating a basic input file."""
        content = """&control
    calculation = 'scf'
/
&system
    ibrav = 0
    nat = 2
    ntyp = 1
    ecutwfc = 30.0
/
"""
        qe_input = QEInputParser.parse_string(content)
        generated = QEInputGenerator.generate(qe_input)
        
        assert "&control" in generated
        assert "calculation = 'scf'" in generated
        assert "&system" in generated
        assert "ecutwfc = 30.0" in generated
    
    def test_roundtrip_parsing(self):
        """Test roundtrip: parse -> generate -> parse."""
        original = """&control
    calculation = 'scf'
    prefix = 'si'
/
&system
    ibrav = 0
    nat = 2
    ntyp = 1
    ecutwfc = 30.0
/
"""
        # Parse
        qe_input1 = QEInputParser.parse_string(original)
        
        # Generate
        generated = QEInputGenerator.generate(qe_input1)
        
        # Parse again
        qe_input2 = QEInputParser.parse_string(generated)
        
        # Compare
        control1 = qe_input1.get_namelist("control")
        control2 = qe_input2.get_namelist("control")
        assert control1.get("calculation") == control2.get("calculation")
        assert control1.get("prefix") == control2.get("prefix")
        
        system1 = qe_input1.get_namelist("system")
        system2 = qe_input2.get_namelist("system")
        assert system1.get("ecutwfc") == system2.get("ecutwfc")

