"""
Unit tests for QE input parser and generator.

These are quick tests that run in CI.
"""

import pytest
from pathlib import Path
import tempfile

from qmatsuite.io import (
    QEInputParser,
    QEInputGenerator,
    QEInput,
    QENamelist,
    QECard,
    QECardType,
)

# Mark all tests in this file as quick
pytestmark = pytest.mark.quick


class TestQEInputParser:
    """Test QE input file parsing."""
    
    def test_parse_simple_scf(self):
        """Test parsing a simple SCF calculation."""
        content = """&control
    calculation = 'scf'
    prefix = 'si'
    pseudo_dir = '/path/to/pseudo'
/
&system
    ibrav=2, celldm(1) =10.20, 
    nat=2, ntyp=1,
    ecutwfc=30.0
/
&electrons
    conv_thr=1.0d-6
/
ATOMIC_SPECIES
Si 28.085 Si.pbe-n-rrkjus.UPF
ATOMIC_POSITIONS alat
Si 0.0 0.0 0.0
Si 0.25 0.25 0.25
K_POINTS gamma
"""
        qe_input = QEInputParser.parse_string(content)
        
        assert len(qe_input.namelists) == 3
        assert qe_input.get_namelist("control") is not None
        assert qe_input.get_namelist("system") is not None
        assert qe_input.get_namelist("electrons") is not None
        
        control = qe_input.get_namelist("control")
        assert control.get("calculation") == "scf"
        assert control.get("prefix") == "si"
    
    def test_parse_namelist_parameters(self):
        """Test parsing namelist parameters."""
        content = """&system
    ibrav = 0,
    nat = 2,
    ntyp = 1,
    ecutwfc = 30.0,
    ecutrho = 120.0
/
"""
        qe_input = QEInputParser.parse_string(content)
        system = qe_input.get_namelist("system")
        
        assert system.get("ibrav") == 0
        assert system.get("nat") == 2
        assert system.get("ntyp") == 1
        assert system.get("ecutwfc") == 30.0
        assert system.get("ecutrho") == 120.0
    
    def test_parse_cards(self):
        """Test parsing cards."""
        content = """ATOMIC_SPECIES
Si 28.085 Si.pbe-n-rrkjus.UPF
O 15.999 O.pbe-n-rrkjus.UPF

ATOMIC_POSITIONS alat
Si 0.0 0.0 0.0
O 0.25 0.25 0.25

K_POINTS gamma
"""
        qe_input = QEInputParser.parse_string(content)
        
        assert len(qe_input.cards) == 3
        
        atomic_species = qe_input.get_card(QECardType.ATOMIC_SPECIES)
        assert atomic_species is not None
        assert len(atomic_species.data) == 2
        
        atomic_positions = qe_input.get_card(QECardType.ATOMIC_POSITIONS)
        assert atomic_positions is not None
        assert atomic_positions.option == "alat"
        assert len(atomic_positions.data) == 2
        
        k_points = qe_input.get_card(QECardType.K_POINTS)
        assert k_points is not None
        assert k_points.option == "gamma"
    
    def test_parse_fortran_d_format(self):
        """Test parsing Fortran double precision format (1.0d-8)."""
        content = """&electrons
    conv_thr = 1.0d-8
    mixing_beta = 0.7d0
/
"""
        qe_input = QEInputParser.parse_string(content)
        electrons = qe_input.get_namelist("electrons")
        
        # Should be parsed as float, not string
        conv_thr = electrons.get("conv_thr")
        assert isinstance(conv_thr, float)
        assert abs(conv_thr - 1e-8) < 1e-10
        
        mixing_beta = electrons.get("mixing_beta")
        assert isinstance(mixing_beta, float)
        assert abs(mixing_beta - 0.7) < 1e-10


class TestQEInputGenerator:
    """Test QE input file generation."""
    
    def test_generate_simple_input(self):
        """Test generating a simple input file."""
        qe_input = QEInput()
        
        control = QENamelist("control")
        control.set("calculation", "scf")
        control.set("prefix", "si")
        qe_input.namelists.append(control)
        
        system = QENamelist("system")
        system.set("ibrav", 0)
        system.set("nat", 2)
        system.set("ntyp", 1)
        system.set("ecutwfc", 30.0)
        qe_input.namelists.append(system)
        
        atomic_species = QECard(QECardType.ATOMIC_SPECIES)
        atomic_species.add_line(["Si", "28.085", "Si.pbe-n-rrkjus.UPF"])
        qe_input.cards.append(atomic_species)
        
        generated = QEInputGenerator.generate(qe_input)
        
        assert "&control" in generated
        assert "calculation = 'scf'" in generated
        assert "&system" in generated
        assert "ATOMIC_SPECIES" in generated
    
    def test_roundtrip_conversion(self):
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
ATOMIC_SPECIES
Si 28.085 Si.pbe-n-rrkjus.UPF
"""
        # Parse
        qe_input1 = QEInputParser.parse_string(original)
        
        # Generate
        generated = QEInputGenerator.generate(qe_input1)
        
        # Parse again
        qe_input2 = QEInputParser.parse_string(generated)
        
        # Compare key parameters
        control1 = qe_input1.get_namelist("control")
        control2 = qe_input2.get_namelist("control")
        assert control1.get("calculation") == control2.get("calculation")
        assert control1.get("prefix") == control2.get("prefix")
        
        system1 = qe_input1.get_namelist("system")
        system2 = qe_input2.get_namelist("system")
        assert system1.get("ecutwfc") == system2.get("ecutwfc")


class TestQEInputFileIO:
    """Test reading and writing input files."""
    
    def test_parse_file(self, tmp_path):
        """Test parsing from file."""
        input_file = tmp_path / "test.in"
        input_file.write_text("""&control
    calculation = 'scf'
/
""")
        
        qe_input = QEInputParser.parse_file(input_file)
        assert qe_input.get_namelist("control") is not None
    
    def test_generate_file(self, tmp_path):
        """Test generating to file."""
        qe_input = QEInput()
        control = QENamelist("control")
        control.set("calculation", "scf")
        qe_input.namelists.append(control)
        
        output_file = tmp_path / "output.in"
        QEInputGenerator.write_file(qe_input, output_file)
        
        assert output_file.exists()
        content = output_file.read_text()
        assert "&control" in content
        assert "calculation" in content
