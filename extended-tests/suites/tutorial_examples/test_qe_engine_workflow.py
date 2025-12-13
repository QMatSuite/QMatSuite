"""
Integration tests for QE engine with tutorial examples.

These tests require downloading tutorial examples and are moved from tests/
to extended-tests/ since they depend on external resources.
"""

import pytest
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from quantumvitas.io import (
    QEInputParser, QEInputGenerator, QEInput, QENamelist, QECard, QECardType
)


class TestRealWorldCalculation:
    """Test real-world calculation scenarios with tutorial examples."""
    
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
    
    def test_workflow_scf_to_nscf(self, examples_dir, tmp_path):
        """Test calculation: SCF -> NSCF -> DOS using 4_Si_DOS examples."""
        dos_dir = examples_dir / "4_Si_DOS"
        
        # Step 1: Parse si.1_scf.in (SCF calculation)
        scf_file = dos_dir / "si.1_scf.in"
        if not scf_file.exists():
            pytest.skip("SCF example not found: si.1_scf.in")
        
        scf_input = QEInputParser.parse_file(scf_file)
        scf_control = scf_input.get_namelist('control')
        assert scf_control is not None
        assert scf_control.get('calculation') == 'scf'
        
        # Step 2: Parse si.2_nscf.in (NSCF calculation)
        nscf_file = dos_dir / "si.2_nscf.in"
        if not nscf_file.exists():
            pytest.skip("NSCF example not found: si.2_nscf.in")
        
        nscf_input = QEInputParser.parse_file(nscf_file)
        nscf_control = nscf_input.get_namelist('control')
        assert nscf_control is not None
        assert nscf_control.get('calculation') == 'nscf'
        
        # Verify NSCF uses same prefix as SCF (calculation dependency)
        scf_prefix = scf_control.get('prefix')
        nscf_prefix = nscf_control.get('prefix')
        assert scf_prefix == nscf_prefix, "NSCF should use same prefix as SCF"
        
        # Step 3: Parse si.3_dos.in (DOS calculation)
        dos_file = dos_dir / "si.3_dos.in"
        if not dos_file.exists():
            pytest.skip("DOS example not found: si.3_dos.in")
        
        dos_input = QEInputParser.parse_file(dos_file)
        # DOS uses &DOS namelist, not &control
        dos_namelist = dos_input.get_namelist('dos')
        assert dos_namelist is not None, "DOS input should have &DOS namelist"
        
        # Verify DOS uses same prefix (calculation dependency)
        dos_prefix = dos_namelist.get('prefix')
        assert dos_prefix == scf_prefix, "DOS should use same prefix as SCF/NSCF"
        
        # Step 4: Test roundtrip generation for each step
        # Generate SCF input
        generated_scf = tmp_path / "si.1_scf_generated.in"
        QEInputGenerator.write_file(scf_input, generated_scf)
        assert generated_scf.exists()
        
        # Generate NSCF input
        generated_nscf = tmp_path / "si.2_nscf_generated.in"
        QEInputGenerator.write_file(nscf_input, generated_nscf)
        assert generated_nscf.exists()
        
        # Generate DOS input
        generated_dos = tmp_path / "si.3_dos_generated.in"
        QEInputGenerator.write_file(dos_input, generated_dos)
        assert generated_dos.exists()
        
        # Verify generated files can be re-parsed
        scf_reparsed = QEInputParser.parse_file(generated_scf)
        assert scf_reparsed.get_namelist('control').get('calculation') == 'scf'
        
        nscf_reparsed = QEInputParser.parse_file(generated_nscf)
        assert nscf_reparsed.get_namelist('control').get('calculation') == 'nscf'
        
        dos_reparsed = QEInputParser.parse_file(generated_dos)
        dos_reparsed_namelist = dos_reparsed.get_namelist('dos')
        assert dos_reparsed_namelist is not None, "Re-parsed DOS should have &DOS namelist"
        assert dos_reparsed_namelist.get('prefix') == scf_prefix
    
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

