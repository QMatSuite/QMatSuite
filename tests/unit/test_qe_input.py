"""
Unit tests for QE input parser and generator.
"""

import pytest
from pathlib import Path
import tempfile

from quantumvitas.core.engines.qe_input import (
    QEInputParser,
    QEInputGenerator,
    QEInput,
    QENamelist,
    QECard,
    QECardType,
)


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
    ecutwfc=20.0
/
&electrons
/
ATOMIC_SPECIES
 Si  28.086  Si.pz-vbc.UPF
ATOMIC_POSITIONS (alat)
 Si 0.00 0.00 0.00
 Si 0.25 0.25 0.25
K_POINTS (automatic)
  6 6 6 0 0 0
"""
        qe_input = QEInputParser.parse_string(content)
        
        # Check namelists
        assert len(qe_input.namelists) == 3
        control = qe_input.get_namelist('control')
        assert control is not None
        assert control.get('calculation') == 'scf'
        assert control.get('prefix') == 'si'
        
        system = qe_input.get_namelist('system')
        assert system is not None
        assert system.get('ibrav') == 2
        assert system.get('celldm(1)') == 10.20
        assert system.get('nat') == 2
        
        # Check cards
        assert len(qe_input.cards) == 3
        
        atomic_species = qe_input.get_card(QECardType.ATOMIC_SPECIES)
        assert atomic_species is not None
        assert len(atomic_species.data) == 1
        assert atomic_species.data[0][0] == 'Si'
        
        atomic_pos = qe_input.get_card(QECardType.ATOMIC_POSITIONS)
        assert atomic_pos is not None
        assert atomic_pos.option == 'alat'
        assert len(atomic_pos.data) == 2
        
        k_points = qe_input.get_card(QECardType.K_POINTS)
        assert k_points is not None
        assert k_points.option == 'automatic'
    
    def test_parse_with_comments(self):
        """Test parsing with comments."""
        content = """&control
    calculation = 'scf'  ! This is a comment
    prefix = 'si'
/
&system
    ibrav=2
    ! Another comment
    nat=2
/
"""
        qe_input = QEInputParser.parse_string(content)
        
        control = qe_input.get_namelist('control')
        assert control.get('calculation') == 'scf'
        assert control.get('prefix') == 'si'
    
    def test_parse_k_points_crystal(self):
        """Test parsing K_POINTS with crystal coordinates."""
        content = """K_POINTS {crystal_b}
5
  0.0000 0.5000 0.0000 20 !L
  0.0000 0.0000 0.0000 30 !Gamma
  -0.500 0.0000 -0.500 10 !X
  -0.375 0.2500 -0.375 30 !U
  0.0000 0.0000 0.0000 20 !Gamma
"""
        qe_input = QEInputParser.parse_string(content)
        
        k_points = qe_input.get_card(QECardType.K_POINTS)
        assert k_points is not None
        assert k_points.option == 'crystal_b'
        assert len(k_points.data) == 6  # n_points + 5 k-point lines
    
    def test_parse_boolean_values(self):
        """Test parsing boolean values."""
        content = """&control
    tprnfor = .true.
    tstress = .false.
    restart_mode = 'from_scratch'
/
"""
        qe_input = QEInputParser.parse_string(content)
        
        control = qe_input.get_namelist('control')
        assert control.get('tprnfor') is True
        assert control.get('tstress') is False
    
    def test_parse_array_values(self):
        """Test parsing array values."""
        content = """&system
    celldm = (10.20, 0.0, 0.0, 0.0, 0.0, 0.0)
    starting_magnetization = (0.5, 0.3)
/
"""
        qe_input = QEInputParser.parse_string(content)
        
        system = qe_input.get_namelist('system')
        celldm = system.get('celldm')
        assert isinstance(celldm, list)
        assert len(celldm) == 6


class TestQEInputGenerator:
    """Test QE input file generation."""
    
    def test_generate_simple_scf(self):
        """Test generating a simple SCF input."""
        qe_input = QEInput()
        
        # Add control namelist
        control = QENamelist(name='control', parameters={
            'calculation': 'scf',
            'prefix': 'si',
            'pseudo_dir': '/path/to/pseudo'
        })
        qe_input.namelists.append(control)
        
        # Add system namelist
        system = QENamelist(name='system', parameters={
            'ibrav': 2,
            'celldm(1)': 10.20,
            'nat': 2,
            'ntyp': 1,
            'ecutwfc': 20.0
        })
        qe_input.namelists.append(system)
        
        # Add electrons namelist
        electrons = QENamelist(name='electrons', parameters={})
        qe_input.namelists.append(electrons)
        
        # Add ATOMIC_SPECIES card
        atomic_species = QECard(
            card_type=QECardType.ATOMIC_SPECIES,
            data=[['Si', '28.086', 'Si.pz-vbc.UPF']]
        )
        qe_input.cards.append(atomic_species)
        
        # Add ATOMIC_POSITIONS card
        atomic_pos = QECard(
            card_type=QECardType.ATOMIC_POSITIONS,
            option='alat',
            data=[['Si', '0.00', '0.00', '0.00'], ['Si', '0.25', '0.25', '0.25']]
        )
        qe_input.cards.append(atomic_pos)
        
        # Add K_POINTS card
        k_points = QECard(
            card_type=QECardType.K_POINTS,
            option='automatic',
            data=[['6', '6', '6', '0', '0', '0']]
        )
        qe_input.cards.append(k_points)
        
        # Generate
        output = QEInputGenerator.generate(qe_input)
        
        # Verify output contains expected content
        assert '&control' in output
        assert "calculation = 'scf'" in output
        assert 'ATOMIC_SPECIES' in output
        assert 'ATOMIC_POSITIONS (alat)' in output
        assert 'K_POINTS (automatic)' in output
    
    def test_generate_boolean_values(self):
        """Test generating boolean values."""
        qe_input = QEInput()
        control = QENamelist(name='control', parameters={
            'tprnfor': True,
            'tstress': False
        })
        qe_input.namelists.append(control)
        
        output = QEInputGenerator.generate(qe_input)
        assert 'tprnfor = .true.' in output
        assert 'tstress = .false.' in output


class TestBidirectionalConversion:
    """Test bidirectional conversion (parse -> generate -> parse)."""
    
    def test_roundtrip_simple(self):
        """Test roundtrip conversion of a simple input."""
        original_content = """&control
    calculation = 'scf'
    prefix = 'si'
    pseudo_dir = '/path/to/pseudo'
/
&system
    ibrav=2, celldm(1) =10.20, 
    nat=2, ntyp=1,
    ecutwfc=20.0
/
&electrons
/
ATOMIC_SPECIES
 Si  28.086  Si.pz-vbc.UPF
ATOMIC_POSITIONS (alat)
 Si 0.00 0.00 0.00
 Si 0.25 0.25 0.25
K_POINTS (automatic)
  6 6 6 0 0 0
"""
        # Parse
        qe_input = QEInputParser.parse_string(original_content)
        
        # Generate
        generated = QEInputGenerator.generate(qe_input)
        
        # Parse again
        qe_input2 = QEInputParser.parse_string(generated)
        
        # Verify key parameters are preserved
        control1 = qe_input.get_namelist('control')
        control2 = qe_input2.get_namelist('control')
        assert control1.get('calculation') == control2.get('calculation')
        assert control1.get('prefix') == control2.get('prefix')
        
        system1 = qe_input.get_namelist('system')
        system2 = qe_input2.get_namelist('system')
        assert system1.get('ibrav') == system2.get('ibrav')
        assert system1.get('nat') == system2.get('nat')
    
    def test_roundtrip_with_file(self, tmp_path):
        """Test roundtrip conversion using actual files."""
        original_file = tmp_path / "original.in"
        original_content = """&control
    calculation = 'scf'
    prefix = 'si'
/
&system
    ibrav=2
    nat=2
    ecutwfc=20.0
/
ATOMIC_SPECIES
 Si  28.086  Si.pz-vbc.UPF
ATOMIC_POSITIONS (alat)
 Si 0.00 0.00 0.00
 Si 0.25 0.25 0.25
K_POINTS (automatic)
  6 6 6 0 0 0
"""
        original_file.write_text(original_content)
        
        # Parse
        qe_input = QEInputParser.parse_file(original_file)
        
        # Generate to new file
        output_file = tmp_path / "output.in"
        QEInputGenerator.write_file(qe_input, output_file)
        
        # Parse output file
        qe_input2 = QEInputParser.parse_file(output_file)
        
        # Verify
        assert qe_input.get_namelist('control').get('calculation') == \
               qe_input2.get_namelist('control').get('calculation')


class TestRealExamples:
    """Test with real QE tutorial examples."""
    
    @pytest.fixture
    def examples_dir(self):
        """Get path to example files."""
        examples_path = Path(__file__).parent.parent / "examples" / "qe_tutorial_examples"
        if not examples_path.exists():
            pytest.skip("Example files not found")
        return examples_path
    
    def test_parse_si_scf(self, examples_dir):
        """Test parsing Si SCF example."""
        input_file = examples_dir / "0_Si_scf" / "si.scf.in"
        if not input_file.exists():
            pytest.skip(f"Example file not found: {input_file}")
        
        qe_input = QEInputParser.parse_file(input_file)
        
        # Verify structure
        assert len(qe_input.namelists) >= 2
        control = qe_input.get_namelist('control')
        assert control is not None
        assert control.get('calculation') == 'scf'
        
        # Verify cards
        atomic_species = qe_input.get_card(QECardType.ATOMIC_SPECIES)
        assert atomic_species is not None
    
    def test_parse_h2_example(self, examples_dir):
        """Test parsing H2 example."""
        input_file = examples_dir / "1_H2" / "h2.scf_apart.in"
        if not input_file.exists():
            pytest.skip(f"Example file not found: {input_file}")
        
        qe_input = QEInputParser.parse_file(input_file)
        
        # Verify
        control = qe_input.get_namelist('control')
        assert control is not None
        
        system = qe_input.get_namelist('system')
        assert system is not None
        assert system.get('nat') == 2
    
    def test_roundtrip_real_examples(self, examples_dir, tmp_path):
        """Test roundtrip conversion on real examples."""
        test_files = [
            "0_Si_scf/si.scf.in",
            "1_H2/h2.scf_apart.in",
        ]
        
        for rel_path in test_files:
            input_file = examples_dir / rel_path
            if not input_file.exists():
                continue
            
            # Parse
            qe_input = QEInputParser.parse_file(input_file)
            
            # Generate
            output_file = tmp_path / f"roundtrip_{Path(rel_path).name}"
            QEInputGenerator.write_file(qe_input, output_file)
            
            # Parse again
            qe_input2 = QEInputParser.parse_file(output_file)
            
            # Verify key parameters preserved
            control1 = qe_input.get_namelist('control')
            control2 = qe_input2.get_namelist('control')
            if control1 and control2:
                assert control1.get('calculation') == control2.get('calculation')
            
            system1 = qe_input.get_namelist('system')
            system2 = qe_input2.get_namelist('system')
            if system1 and system2:
                assert system1.get('nat') == system2.get('nat')

