"""
Integration tests for QE engine with input generation.
"""

import pytest
from pathlib import Path
import tempfile

from quantumvitas.core.engines.qe import QuantumEspressoEngine
from quantumvitas.core.engines.base import EngineConfig
from quantumvitas.io import (
    QEInputParser, QEInputGenerator, QEInput, QENamelist, QECard, QECardType
)


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


# TestRealWorldWorkflow class moved to extended-tests/suites/tutorial_examples/test_qe_engine_workflow.py
# These tests require downloading tutorial examples and are now in extended-tests/

