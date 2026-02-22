"""
Roundtrip tests for Wannier90 input parser and generator.

Tests that Wannier90 .win and .pw2wan files can be:
1. Parsed from file/string
2. Regenerated from the parsed object
3. Re-parsed and verified to match original
"""

import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from qmatsuite.io.wannier90_input import (
    Wannier90Input,
    Pw2Wannier90Input,
    generate_kpoints_from_mp_grid,
)


REPO_ROOT = Path(__file__).parent.parent.parent
EXAMPLE_DIR = REPO_ROOT / "tests" / "data" / "wannier90_examples" / "example05"


class TestWannier90InputRoundtrip:
    """Test Wannier90 .win file roundtrip parsing and generation."""
    
    def test_roundtrip_diamond_example(self, tmp_path):
        """Test roundtrip with the actual diamond.win example file."""
        example_file = EXAMPLE_DIR / "diamond.win"
        if not example_file.exists():
            pytest.skip(f"Example file not found: {example_file}")
        
        # Read original content
        original_content = example_file.read_text()
        
        # Parse
        w90_input1 = Wannier90Input.from_string(original_content)
        
        # Verify key parameters are parsed correctly
        assert w90_input1.num_wann == 4
        assert w90_input1.num_iter == 20
        assert w90_input1.mp_grid == [4, 4, 4]
        assert len(w90_input1.atoms_frac) == 2
        assert len(w90_input1.kpoints) == 64  # 4x4x4 = 64 kpoints
        
        # Generate
        generated_content = w90_input1.to_string()
        
        # Write to file and verify no QE contamination
        generated_file = tmp_path / "diamond_generated.win"
        w90_input1.write(generated_file)
        
        # Verify file doesn't contain QE syntax
        generated_text = generated_file.read_text()
        assert "&control" not in generated_text.lower()
        assert "outdir" not in generated_text.lower() or "outdir" in generated_text.lower() and "&" not in generated_text
        assert "pseudo_dir" not in generated_text
        assert "&system" not in generated_text.lower()
        assert "END (" not in generated_text  # Should be lowercase "end"
        
        # Re-parse generated content
        w90_input2 = Wannier90Input.from_string(generated_content)
        
        # Verify roundtrip preserves key parameters
        assert w90_input2.num_wann == w90_input1.num_wann
        assert w90_input2.num_iter == w90_input1.num_iter
        assert w90_input2.mp_grid == w90_input1.mp_grid
        assert len(w90_input2.atoms_frac) == len(w90_input1.atoms_frac)
        assert len(w90_input2.kpoints) == len(w90_input1.kpoints)
        assert w90_input2.projections_block == w90_input1.projections_block
    
    def test_roundtrip_minimal_win(self, tmp_path):
        """Test roundtrip with minimal .win file."""
        original_content = """num_wann        = 4
num_iter        = 20

begin atoms_frac
C   -0.125000   -0.125000   -0.125000
C    0.125000    0.125000    0.125000
end atoms_frac

begin projections
f=0.0,0.0,0.0:s
end projections

begin unit_cell_cart
-1.613990   0.000000   1.613990
 0.000000   1.613990   1.613990
-1.613990   1.613990   0.000000
end unit_cell_cart

mp_grid : 4 4 4

begin kpoints
0.0000  0.0000  0.0000
0.0000  0.0000  0.2500
0.0000  0.2500  0.0000
0.2500  0.0000  0.0000
end kpoints
"""
        # Parse
        w90_input1 = Wannier90Input.from_string(original_content)
        
        # Generate
        generated_content = w90_input1.to_string()
        
        # Verify structure
        assert "num_wann" in generated_content
        assert "begin atoms_frac" in generated_content
        assert "end atoms_frac" in generated_content
        assert "begin kpoints" in generated_content
        assert "end kpoints" in generated_content
        assert "&control" not in generated_content.lower()
        assert "END (" not in generated_content
        
        # Re-parse
        w90_input2 = Wannier90Input.from_string(generated_content)
        
        # Verify roundtrip
        assert w90_input2.num_wann == w90_input1.num_wann
        assert w90_input2.mp_grid == w90_input1.mp_grid
    
    def test_roundtrip_no_qe_contamination(self, tmp_path):
        """Test that generated .win file doesn't contain QE syntax."""
        w90_input = Wannier90Input()
        w90_input.seedname = "test"
        w90_input.num_wann = 4
        w90_input.num_iter = 20
        w90_input.mp_grid = [4, 4, 4]
        w90_input.kpoints = generate_kpoints_from_mp_grid([4, 4, 4])
        w90_input.atoms_frac = [
            ["C", -0.125, -0.125, -0.125],
            ["C", 0.125, 0.125, 0.125],
        ]
        w90_input.projections_block = "f=0.0,0.0,0.0:s"
        w90_input.unit_cell_cart = [
            [-1.613990, 0.000000, 1.613990],
            [0.000000, 1.613990, 1.613990],
            [-1.613990, 1.613990, 0.000000],
        ]
        
        # Try to contaminate with QE parameters (should be filtered)
        w90_input.extra_parameters["outdir"] = "./outdir"
        w90_input.extra_parameters["pseudo_dir"] = "/path/to/pseudo"
        w90_input.extra_lines = "&control\noutdir = './outdir'\n/"
        
        # Generate
        generated_content = w90_input.to_string()
        
        # Verify QE syntax is filtered out
        assert "&control" not in generated_content
        assert "outdir = './outdir'" not in generated_content
        assert "pseudo_dir" not in generated_content
        assert "/" not in generated_content or "end" in generated_content  # Only "end" lines should have "/"
        
        # Verify Wannier90 syntax is present
        assert "num_wann" in generated_content
        assert "begin atoms_frac" in generated_content
        assert "end atoms_frac" in generated_content
        
        # Write to file
        output_file = tmp_path / "test.win"
        w90_input.write(output_file)
        
        # Verify file content
        file_content = output_file.read_text()
        assert "&control" not in file_content
        assert "outdir = './outdir'" not in file_content
    
    def test_roundtrip_preserves_kpoints(self, tmp_path):
        """Test that kpoints are correctly preserved in roundtrip."""
        w90_input = Wannier90Input()
        w90_input.num_wann = 4
        w90_input.mp_grid = [4, 4, 4]
        w90_input.kpoints = generate_kpoints_from_mp_grid([4, 4, 4])
        
        # Generate
        generated = w90_input.to_string()
        
        # Verify kpoints block is present
        assert "begin kpoints" in generated
        assert "end kpoints" in generated
        
        # Count kpoints in generated content
        lines = generated.split("\n")
        in_kpoints_block = False
        kpoint_count = 0
        for line in lines:
            if "begin kpoints" in line.lower():
                in_kpoints_block = True
            elif "end kpoints" in line.lower():
                in_kpoints_block = False
            elif in_kpoints_block and line.strip():
                kpoint_count += 1
        
        assert kpoint_count == 64, f"Expected 64 kpoints, found {kpoint_count}"
        
        # Re-parse
        w90_input2 = Wannier90Input.from_string(generated)
        assert len(w90_input2.kpoints) == 64
    
    def test_generate_kpoints_from_mp_grid(self):
        """Test kpoints generation from mp_grid."""
        # 4x4x4 grid should give 64 kpoints
        kpoints = generate_kpoints_from_mp_grid([4, 4, 4])
        assert len(kpoints) == 64
        
        # Verify first and last kpoints
        assert kpoints[0] == [0.0, 0.0, 0.0]
        assert kpoints[-1] == [0.75, 0.75, 0.75]
        
        # Verify kpoints are in [0, 1) range
        for kpt in kpoints:
            assert all(0.0 <= coord < 1.0 for coord in kpt)
        
        # 2x2x2 grid should give 8 kpoints
        kpoints_2x2 = generate_kpoints_from_mp_grid([2, 2, 2])
        assert len(kpoints_2x2) == 8


class TestPw2Wannier90InputRoundtrip:
    """Test pw2wannier90 .pw2wan file roundtrip parsing and generation."""
    
    def test_roundtrip_pw2wan_example(self, tmp_path):
        """Test roundtrip with actual .pw2wan example file."""
        example_file = EXAMPLE_DIR / "diamond.pw2wan"
        if not example_file.exists():
            pytest.skip(f"Example file not found: {example_file}")
        
        # Read original content
        original_content = example_file.read_text()
        
        # Parse
        pw2wan_input1 = Pw2Wannier90Input.from_string(original_content)
        
        # Generate
        generated_content = pw2wan_input1.to_string()
        
        # Write to file
        generated_file = tmp_path / "diamond_generated.pw2wan"
        pw2wan_input1.write(generated_file)
        
        # Re-parse
        pw2wan_input2 = Pw2Wannier90Input.from_string(generated_content)
        
        # Verify roundtrip
        assert pw2wan_input2.seedname == pw2wan_input1.seedname
        assert pw2wan_input2.prefix == pw2wan_input1.prefix
        assert pw2wan_input2.outdir == pw2wan_input1.outdir
        assert pw2wan_input2.write_mmn == pw2wan_input1.write_mmn
        assert pw2wan_input2.write_amn == pw2wan_input1.write_amn
    
    def test_roundtrip_minimal_pw2wan(self):
        """Test roundtrip with minimal .pw2wan file."""
        original_content = """&inputpp
   outdir = './outdir'
   prefix = 'pwscf'
   seedname = 'diamond'
   spin_component = 'none'
   write_mmn = .true.
   write_amn = .true.
   write_unk = .false.
/
"""
        # Parse
        pw2wan_input1 = Pw2Wannier90Input.from_string(original_content)
        
        # Generate
        generated_content = pw2wan_input1.to_string()
        
        # Verify structure
        assert "&inputpp" in generated_content
        assert "outdir" in generated_content
        assert "prefix" in generated_content
        assert "seedname" in generated_content
        
        # Re-parse
        pw2wan_input2 = Pw2Wannier90Input.from_string(generated_content)
        
        # Verify roundtrip
        assert pw2wan_input2.prefix == pw2wan_input1.prefix
        assert pw2wan_input2.seedname == pw2wan_input1.seedname

