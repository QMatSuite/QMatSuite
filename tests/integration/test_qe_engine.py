"""
Integration tests for QE engine with input generation.
"""

import pytest
from pathlib import Path
import tempfile

from quantumvitas.core.engines.qe import QuantumEspressoEngine
from quantumvitas.core.engines.base import EngineConfig
from quantumvitas.core.engines.qe_input import QEInputParser, QEInputGenerator


class TestQEEngineInputGeneration:
    """Test QE engine input generation."""
    
    @pytest.fixture
    def engine(self):
        """Create a QE engine instance."""
        config = EngineConfig(name="qe")
        return QuantumEspressoEngine(config)
    
    def test_generate_input_from_data(self, engine, tmp_path):
        """Test generating input from structured data."""
        input_data = {
            'namelists': {
                'control': {
                    'calculation': 'scf',
                    'prefix': 'test',
                    'pseudo_dir': '/path/to/pseudo'
                },
                'system': {
                    'ibrav': 0,
                    'nat': 2,
                    'ntyp': 1,
                    'ecutwfc': 30.0
                }
            },
            'cards': [
                {
                    'type': 'ATOMIC_SPECIES',
                    'data': [['H', '1.00784', 'H.UPF']]
                },
                {
                    'type': 'ATOMIC_POSITIONS',
                    'option': 'angstrom',
                    'data': [['H', '0.0', '0.0', '0.0'], ['H', '0.74', '0.0', '0.0']]
                },
                {
                    'type': 'K_POINTS',
                    'option': 'automatic',
                    'data': [['1', '1', '1', '0', '0', '0']]
                }
            ]
        }
        
        input_file = engine.generate_input(
            step_type='scf',
            input_data=input_data,
            working_dir=tmp_path
        )
        
        assert input_file.exists()
        
        # Verify file content
        content = input_file.read_text()
        assert '&control' in content
        assert "calculation = 'scf'" in content
        assert 'ATOMIC_SPECIES' in content
    
    def test_parse_input_file(self, engine, tmp_path):
        """Test parsing an input file."""
        # Create a test input file
        input_file = tmp_path / "test.in"
        input_file.write_text("""&control
    calculation = 'scf'
    prefix = 'test'
/
&system
    nat=2
    ecutwfc=30.0
/
ATOMIC_SPECIES
 H  1.00784  H.UPF
""")
        
        qe_input = engine.parse_input_file(input_file)
        
        assert qe_input is not None
        control = qe_input.get_namelist('control')
        assert control.get('calculation') == 'scf'
    
    def test_modify_input_file(self, engine, tmp_path):
        """Test modifying an input file."""
        # Create original input
        original_file = tmp_path / "original.in"
        original_file.write_text("""&control
    calculation = 'scf'
    prefix = 'test'
/
&system
    ecutwfc=30.0
/
""")
        
        # Modify and write
        output_file = tmp_path / "modified.in"
        modifications = {
            'namelists': {
                'control': {'prefix': 'modified'},
                'system': {'ecutwfc': 50.0}
            }
        }
        
        engine.generate_input_from_file(
            original_file,
            output_file,
            modifications=modifications
        )
        
        # Verify modifications
        qe_input = engine.parse_input_file(output_file)
        control = qe_input.get_namelist('control')
        assert control.get('prefix') == 'modified'
        
        system = qe_input.get_namelist('system')
        assert system.get('ecutwfc') == 50.0


class TestRealWorldWorkflow:
    """Test real-world workflow scenarios."""
    
    @pytest.fixture
    def examples_dir(self):
        """Get path to example files."""
        examples_path = Path(__file__).parent.parent / "examples" / "qe_tutorial_examples"
        if not examples_path.exists():
            pytest.skip("Example files not found")
        return examples_path
    
    def test_workflow_scf_to_nscf(self, examples_dir, tmp_path):
        """Test workflow: parse SCF, modify for NSCF."""
        # Find an SCF input
        scf_file = examples_dir / "4_Si_DOS" / "si.scf.in"
        if not scf_file.exists():
            pytest.skip("SCF example not found")
        
        # Parse SCF
        qe_input = QEInputParser.parse_file(scf_file)
        
        # Modify for NSCF
        control = qe_input.get_namelist('control')
        if control:
            control.set('calculation', 'nscf')
        
        system = qe_input.get_namelist('system')
        if system:
            system.set('occupations', 'tetrahedra')
        
        # Generate NSCF input
        nscf_file = tmp_path / "si.nscf.in"
        QEInputGenerator.write_file(qe_input, nscf_file)
        
        # Verify
        nscf_input = QEInputParser.parse_file(nscf_file)
        nscf_control = nscf_input.get_namelist('control')
        assert nscf_control.get('calculation') == 'nscf'
    
    def test_extract_structure_info(self, examples_dir):
        """Test extracting structure information from input."""
        input_file = examples_dir / "0_Si_scf" / "si.scf.in"
        if not input_file.exists():
            pytest.skip("Example file not found")
        
        qe_input = QEInputParser.parse_file(input_file)
        
        # Extract atomic species
        atomic_species = qe_input.get_card(QECardType.ATOMIC_SPECIES)
        if atomic_species:
            species_info = {}
            for line in atomic_species.data:
                if len(line) >= 3:
                    element = line[0]
                    mass = line[1]
                    pseudo = line[2]
                    species_info[element] = {'mass': mass, 'pseudo': pseudo}
            
            assert len(species_info) > 0
        
        # Extract atomic positions
        atomic_pos = qe_input.get_card(QECardType.ATOMIC_POSITIONS)
        if atomic_pos:
            positions = []
            for line in atomic_pos.data:
                if len(line) >= 4:
                    positions.append({
                        'element': line[0],
                        'x': float(line[1]),
                        'y': float(line[2]),
                        'z': float(line[3])
                    })
            
            assert len(positions) > 0

