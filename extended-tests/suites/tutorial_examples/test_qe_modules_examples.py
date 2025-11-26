"""
Unit tests for QE module detection using tutorial examples.

These tests require downloading tutorial examples and are moved from tests/
to extended-tests/ since they depend on external resources.
"""

import pytest
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from quantumvitas.io import QEInputParser, QEInputGenerator, QEModule
from quantumvitas.core.engines.qe import QuantumEspressoEngine
from quantumvitas.core.engines.base import EngineConfig


class TestRealModuleExamples:
    """Test module detection with real example files."""
    
    @pytest.fixture
    def examples_dir(self):
        """Get path to example files."""
        # Use auto-downloaded tutorial examples
        project_root = Path(__file__).parent.parent.parent
        sys.path.insert(0, str(project_root / "extended-tests"))
        from utils.download_tutorial_examples import ensure_tutorial_examples
        examples_path = ensure_tutorial_examples()
        if not examples_path.exists():
            pytest.skip("Example files not found. Run ensure_tutorial_examples() to download.")
        return examples_path
    
    def test_parse_ph_input(self, examples_dir):
        """Test parsing ph.x input file."""
        ph_file = examples_dir / "9_Si_phonon" / "1_gamma_point" / "si.2_ph.in"
        if not ph_file.exists():
            pytest.skip(f"Example file not found: {ph_file}")
        
        qe_input = QEInputParser.parse_file(ph_file)
        
        # Verify it's detected as ph.x
        assert qe_input.module == QEModule.PH
        
        # Verify namelists
        inputph = qe_input.get_namelist("inputph")
        assert inputph is not None
        assert inputph.get('prefix') == 'si'
    
    def test_parse_gipaw_input(self, examples_dir):
        """Test parsing gipaw.x input file."""
        gipaw_file = examples_dir / "12_NMR_gipaw" / "2_benzene" / "benzene.2_gipaw.in"
        if not gipaw_file.exists():
            pytest.skip(f"Example file not found: {gipaw_file}")
        
        qe_input = QEInputParser.parse_file(gipaw_file)
        
        # Verify it's detected as gipaw.x
        assert qe_input.module == QEModule.GIPAW
        
        # Verify namelists
        inputgipaw = qe_input.get_namelist("inputgipaw")
        assert inputgipaw is not None
        assert inputgipaw.get('job') == 'nmr'
    
    def test_roundtrip_ph_module(self, examples_dir, tmp_path):
        """Test roundtrip conversion for ph.x input."""
        ph_file = examples_dir / "9_Si_phonon" / "1_gamma_point" / "si.2_ph.in"
        if not ph_file.exists():
            pytest.skip(f"Example file not found: {ph_file}")
        
        # Parse
        qe_input = QEInputParser.parse_file(ph_file)
        
        # Generate
        output_file = tmp_path / "ph_roundtrip.in"
        QEInputGenerator.write_file(qe_input, output_file)
        
        # Re-parse
        qe_input2 = QEInputParser.parse_file(output_file)
        
        # Verify module detection still works
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
        
        # Generate
        output_file = tmp_path / "gipaw_roundtrip.in"
        QEInputGenerator.write_file(qe_input, output_file)
        
        # Re-parse
        qe_input2 = QEInputParser.parse_file(output_file)
        
        # Verify module detection still works
        assert qe_input2.module == QEModule.GIPAW
        
        # Verify key parameters
        inputgipaw1 = qe_input.get_namelist('inputgipaw')
        inputgipaw2 = qe_input2.get_namelist('inputgipaw')
        assert inputgipaw1.get('job') == inputgipaw2.get('job')


class TestQEEngineModuleSupport:
    """Test QE engine module support with real examples."""
    
    @pytest.fixture
    def examples_dir(self):
        """Get path to example files."""
        project_root = Path(__file__).parent.parent.parent
        sys.path.insert(0, str(project_root / "extended-tests"))
        from utils.download_tutorial_examples import ensure_tutorial_examples
        examples_path = ensure_tutorial_examples()
        if not examples_path.exists():
            pytest.skip("Example files not found. Run ensure_tutorial_examples() to download.")
        return examples_path
    
    @pytest.fixture
    def engine(self):
        """Create a QE engine instance."""
        config = EngineConfig(name="qe")
        return QuantumEspressoEngine(config)
    
    def test_detect_module_from_file(self, engine, examples_dir):
        """Test detecting module from input file."""
        ph_file = examples_dir / "9_Si_phonon" / "1_gamma_point" / "si.2_ph.in"
        if not ph_file.exists():
            pytest.skip("Example file not found")
        
        qe_input = engine.parse_input_file(ph_file)
        # Module detection is done by QEInput, not engine
        # But we can verify the input was parsed correctly
        assert qe_input is not None
        assert qe_input.get_namelist("inputph") is not None
    
    def test_generate_ph_input(self, engine, examples_dir, tmp_path):
        """Test generating ph.x input."""
        ph_file = examples_dir / "9_Si_phonon" / "1_gamma_point" / "si.2_ph.in"
        if not ph_file.exists():
            pytest.skip("Example file not found")
        
        # Parse original
        qe_input = engine.parse_input_file(ph_file)
        
        # Generate new file
        output_file = tmp_path / "ph_generated.in"
        QEInputGenerator.write_file(qe_input, output_file)
        
        # Verify
        assert output_file.exists()
        content = output_file.read_text()
        assert "&inputph" in content
    
    def test_generate_gipaw_input(self, engine, examples_dir, tmp_path):
        """Test generating gipaw.x input."""
        gipaw_file = examples_dir / "12_NMR_gipaw" / "2_benzene" / "benzene.2_gipaw.in"
        if not gipaw_file.exists():
            pytest.skip("Example file not found")
        
        # Parse original
        qe_input = engine.parse_input_file(gipaw_file)
        
        # Generate new file
        output_file = tmp_path / "gipaw_generated.in"
        QEInputGenerator.write_file(qe_input, output_file)
        
        # Verify
        assert output_file.exists()
        content = output_file.read_text()
        assert "&inputgipaw" in content

