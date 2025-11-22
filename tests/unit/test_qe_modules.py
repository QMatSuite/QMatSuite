"""
Unit tests for QE module detection and multi-module support.
"""

import pytest
from pathlib import Path

from quantumvitas.core.engines.qe_input import (
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


class TestRealModuleExamples:
    """Test with real example files from different modules."""
    
    @pytest.fixture
    def examples_dir(self):
        """Get path to example files."""
        # Use auto-downloaded tutorial examples
        import sys
        from pathlib import Path
        project_root = Path(__file__).parent.parent.parent
        sys.path.insert(0, str(project_root / "extended-tests"))
        from utils.download_tutorial_examples import ensure_tutorial_examples
        examples_path = ensure_tutorial_examples()
        if not examples_path.exists():
            pytest.skip("Example files not found")
        return examples_path
    
    def test_parse_ph_input(self, examples_dir):
        """Test parsing ph.x input file."""
        ph_file = examples_dir / "9_Si_phonon" / "1_gamma_point" / "si.2_ph.in"
        if not ph_file.exists():
            pytest.skip(f"Example file not found: {ph_file}")
        
        qe_input = QEInputParser.parse_file(ph_file)
        
        assert qe_input.module == QEModule.PH
        inputph = qe_input.get_namelist('inputph')
        assert inputph is not None
        assert inputph.get('prefix') == 'si'
    
    def test_parse_gipaw_input(self, examples_dir):
        """Test parsing gipaw.x input file."""
        gipaw_file = examples_dir / "12_NMR_gipaw" / "2_benzene" / "benzene.2_gipaw.in"
        if not gipaw_file.exists():
            pytest.skip(f"Example file not found: {gipaw_file}")
        
        qe_input = QEInputParser.parse_file(gipaw_file)
        
        assert qe_input.module == QEModule.GIPAW
        inputgipaw = qe_input.get_namelist('inputgipaw')
        assert inputgipaw is not None
        assert inputgipaw.get('job') == 'nmr'
    
    def test_roundtrip_ph_module(self, examples_dir, tmp_path):
        """Test roundtrip conversion for ph.x input."""
        ph_file = examples_dir / "9_Si_phonon" / "1_gamma_point" / "si.2_ph.in"
        if not ph_file.exists():
            pytest.skip(f"Example file not found: {ph_file}")
        
        # Parse
        qe_input = QEInputParser.parse_file(ph_file)
        assert qe_input.module == QEModule.PH
        
        # Generate
        output_file = tmp_path / "ph_roundtrip.in"
        QEInputGenerator.write_file(qe_input, output_file)
        
        # Parse again
        qe_input2 = QEInputParser.parse_file(output_file)
        assert qe_input2.module == QEModule.PH
        
        # Verify key parameters
        inputph1 = qe_input.get_namelist('inputph')
        inputph2 = qe_input2.get_namelist('inputph')
        assert inputph1.get('prefix') == inputph2.get('prefix')
    
    def test_roundtrip_gipaw_module(self, examples_dir, tmp_path):
        """Test roundtrip conversion for gipaw.x input."""
        gipaw_file = examples_dir / "12_NMR_gipaw" / "2_benzene" / "benzene.2_gipaw.in"
        if not gipaw_file.exists():
            pytest.skip(f"Example file not found: {gipaw_file}")
        
        # Parse
        qe_input = QEInputParser.parse_file(gipaw_file)
        assert qe_input.module == QEModule.GIPAW
        
        # Generate
        output_file = tmp_path / "gipaw_roundtrip.in"
        QEInputGenerator.write_file(qe_input, output_file)
        
        # Parse again
        qe_input2 = QEInputParser.parse_file(output_file)
        assert qe_input2.module == QEModule.GIPAW
        
        # Verify key parameters
        inputgipaw1 = qe_input.get_namelist('inputgipaw')
        inputgipaw2 = qe_input2.get_namelist('inputgipaw')
        assert inputgipaw1.get('job') == inputgipaw2.get('job')


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
            step_type='ph',
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
            step_type='gipaw',
            input_data=input_data,
            working_dir=tmp_path
        )
        
        assert input_file.exists()
        
        # Verify it's detected as GIPAW module
        qe_input = engine.parse_input_file(input_file)
        assert qe_input.module == QEModule.GIPAW

