"""Unit tests for LAMMPS potential staging."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from qmatsuite.core.resources import get_resources_dir
from qmatsuite.engine.lammps_potentials import (
    stage_potentials,
    compute_potential_digest,
    generate_pair_style_block,
    validate_custom_script_assets,
)


class TestPotentialStaging:
    """Test potential file staging."""
    
    def test_compute_potential_digest(self):
        """Test potential digest computation."""
        test_files = [
            ("test.eam", get_resources_dir() / "lammps" / "potentials" / "Cu_u3.eam"),
        ]
        staged = [(name, path) for name, path in test_files if path.exists()]
        
        if staged:
            digest = compute_potential_digest(staged)
            assert len(digest) == 64, "Digest should be SHA256 (64 hex chars)"
            print(f"✓ Potential digest computed: {digest[:16]}...")
        else:
            pytest.skip("Potential file not found")
    
    def test_generate_pair_style_block_lj(self):
        """Test generating pair_style block for LJ."""
        pot_def = {
            "style": "lj/cut",
            "cutoff": 2.5,
            "params": {
                "1 1": "1.0 1.0",
            },
        }
        
        from pymatgen.core import Structure, Lattice
        structure = Structure(Lattice.cubic(3.6), ["Ar"], [[0, 0, 0]])
        
        block = generate_pair_style_block(pot_def, [], structure)
        assert "pair_style lj/cut" in block
        assert "pair_coeff" in block
        print("✓ LJ pair_style block generated")
    
    def test_generate_pair_style_block_eam(self):
        """Test generating pair_style block for EAM."""
        pot_def = {
            "style": "eam",
        }
        
        staged_files = [("Cu_u3.eam", Path("/tmp/Cu_u3.eam"))]
        
        from pymatgen.core import Structure, Lattice
        structure = Structure(Lattice.cubic(3.6), ["Cu"], [[0, 0, 0]])
        
        block = generate_pair_style_block(pot_def, staged_files, structure, potentials_dir="potentials")
        assert "pair_style eam" in block
        assert "potentials/Cu_u3.eam" in block
        print("✓ EAM pair_style block generated")
    
    def test_validate_custom_script_assets(self):
        """Test custom script asset validation."""
        # Should pass when custom_script not present
        validate_custom_script_assets({})
        
        # Should pass when required_files present
        validate_custom_script_assets({
            "custom_script": {"content": "test"},
            "assets": {"required_files": ["potentials/test.eam"]},
        })
        
        # Should fail when custom_script present but required_files missing
        with pytest.raises(ValueError, match="required_files"):
            validate_custom_script_assets({
                "custom_script": {"content": "test"},
            })
        
        print("✓ Custom script validation works")
