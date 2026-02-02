"""
Unit tests for QE module detection and multi-module support.
"""

import pytest
from pathlib import Path

from quantumvitas.io import (
    QEInputParser,
    QEInputGenerator,
    QEModule,
)
from quantumvitas.core.engines.qe import QuantumEspressoEngine
from quantumvitas.core.engines.base import EngineConfig


class TestQEModuleDetection:
    """Test QE module detection from input files."""
    
    def test_detect_pw_module(self):
        """Test detection of pw.x module."""
        content = """&control
    calculation = 'scf'
    prefix = 'si'
/
&system
    nat=2
    ecutwfc=30.0
/
&electrons
/
ATOMIC_SPECIES
 Si  28.086  Si.UPF
"""
        qe_input = QEInputParser.parse_string(content)
        assert qe_input.module == QEModule.PW
    
    def test_detect_ph_module(self):
        """Test detection of ph.x module."""
        content = """&inputph
  outdir = './outdir'
  prefix = 'si',
  tr2_ph = 1.0d-14
  epsil = .true.
/
0 0 0
"""
        qe_input = QEInputParser.parse_string(content)
        assert qe_input.module == QEModule.PH
    
    def test_detect_gipaw_module(self):
        """Test detection of gipaw.x module."""
        content = """&inputgipaw
    job = 'nmr'
    prefix = 'benzene'
    tmp_dir = './outdir/'
    restart_mode = 'from_scratch'
/
"""
        qe_input = QEInputParser.parse_string(content)
        assert qe_input.module == QEModule.GIPAW
    
    def test_detect_neb_module(self):
        """Test detection of neb.x module."""
        content = """&PATH
  restart_mode = 'from_scratch'
  string_method = 'neb',
  nstep_path = 150,
/
"""
        qe_input = QEInputParser.parse_string(content)
        assert qe_input.module == QEModule.NEB


# TestRealModuleExamples class moved to extended-tests/suites/tutorial_examples/test_qe_modules_examples.py
# These tests require downloading tutorial examples and are now in extended-tests/


class TestQEEngineModuleSupport:
    """Test QE engine support for different modules."""
    
    @pytest.fixture
    def engine(self):
        """Create a QE engine instance."""
        config = EngineConfig(name="qe")
        return QuantumEspressoEngine(config)
    
    def test_detect_module_from_file(self, engine, tmp_path):
        """Test module detection from file."""
        # Create ph.x input
        ph_content = """&inputph
  prefix = 'test'
  outdir = './outdir'
/
"""
        ph_file = tmp_path / "test_ph.in"
        ph_file.write_text(ph_content)
        
        module = engine.detect_module_from_input(ph_file)
        assert module == QEModule.PH
    
    def test_generate_ph_input(self, engine, tmp_path):
        """Test generating ph.x input."""
        input_data = {
            'namelists': {
                'inputph': {
                    'prefix': 'si',
                    'outdir': './outdir',
                    'tr2_ph': 1.0e-14,
                    'epsil': True
                }
            }
        }
        
        input_file = engine.generate_input(
            step_type_gen='ph',
            input_data=input_data,
            working_dir=tmp_path
        )
        
        assert input_file.exists()
        
        # Verify it's detected as PH module
        qe_input = engine.parse_input_file(input_file)
        assert qe_input.module == QEModule.PH
    
    def test_generate_gipaw_input(self, engine, tmp_path):
        """Test generating gipaw.x input."""
        input_data = {
            'namelists': {
                'inputgipaw': {
                    'job': 'nmr',
                    'prefix': 'benzene',
                    'tmp_dir': './outdir/',
                    'restart_mode': 'from_scratch'
                }
            }
        }
        
        input_file = engine.generate_input(
            step_type_gen='custom',  # Use 'custom' for unsupported step types like 'gipaw'
            input_data=input_data,
            working_dir=tmp_path
        )
        
        assert input_file.exists()
        
        # Verify it's detected as GIPAW module
        qe_input = engine.parse_input_file(input_file)
        assert qe_input.module == QEModule.GIPAW

