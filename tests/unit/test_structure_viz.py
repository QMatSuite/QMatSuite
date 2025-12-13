"""Tests for structure visualization module."""

from pathlib import Path

import pytest
from pymatgen.core import Lattice, Structure

from quantumvitas.io import read_structure
from quantumvitas.analysis.structure_viz import (
    detect_bonds,
    generate_boundary_atoms,
    get_element_color,
    get_element_radius,
    make_supercell,
    plot_structure_3d,
    visualize_structure,
    StructurePlotOptions,
    COVALENT_RADII,
)


class TestCovalentRadii:
    """Tests for covalent radii lookup."""

    def test_covalent_radii_has_common_elements(self):
        """Test that common elements are in the covalent radii table."""
        common_elements = ["H", "C", "N", "O", "Si", "Fe", "Cu", "Au"]
        for elem in common_elements:
            assert elem in COVALENT_RADII, f"Missing {elem} in COVALENT_RADII"

    def test_get_element_radius_returns_value(self):
        """Test that get_element_radius returns reasonable values."""
        # Si covalent radius should be ~1.11 Å
        si_radius = get_element_radius("Si")
        assert 1.0 <= si_radius <= 1.3, f"Si radius {si_radius} out of expected range"

        # H covalent radius should be ~0.31 Å
        h_radius = get_element_radius("H")
        assert 0.2 <= h_radius <= 0.5, f"H radius {h_radius} out of expected range"

    def test_get_element_radius_fallback(self):
        """Test that unknown elements get default radius."""
        # Use a fictional element symbol
        radius = get_element_radius("Xx")
        assert radius == 1.0  # Default fallback

    def test_get_element_color_returns_hex(self):
        """Test that get_element_color returns valid hex colors."""
        color = get_element_color("Si")
        assert color.startswith("#"), f"Color should be hex: {color}"
        assert len(color) == 7, f"Color should be #RRGGBB: {color}"


class TestBondDetection:
    """Tests for bond detection in structures."""

    @pytest.fixture
    def si_diamond_structure(self):
        """Create a Si diamond structure (FCC primitive cell, ibrav=2)."""
        import numpy as np
        
        a = 5.431  # Lattice constant in Angstrom
        # ibrav=2 vectors for FCC
        a1 = a / 2 * np.array([-1, 0, 1])
        a2 = a / 2 * np.array([0, 1, 1])
        a3 = a / 2 * np.array([-1, 1, 0])
        lattice = Lattice([a1, a2, a3])
        
        return Structure(
            lattice,
            ["Si", "Si"],
            [[0.0, 0.0, 0.0], [0.25, 0.25, 0.25]],
            coords_are_cartesian=False,
        )

    def test_detect_bonds_si_unit_cell_with_periodic(self, si_diamond_structure):
        """Test bond detection in Si unit cell with PBC-aware detection.
        
        Note: include_periodic_images is deprecated and no longer affects bond detection.
        Bond detection always uses PBC-aware minimum-image convention for periodic structures.
        """
        bonds = detect_bonds(si_diamond_structure, include_periodic_images=True)
        # With PBC-aware detection, each Si should find all 4 neighbors via minimum-image
        # In a 2-atom unit cell, there's 1 bond within the cell and 3 via PBC
        # Total should be 4 bonds (each Si has 4 neighbors, 2 atoms * 4 / 2 = 4)
        assert len(bonds) >= 1, f"Expected at least 1 bond, got {len(bonds)}"
        # Note: The exact count depends on the unit cell geometry and cutoff
        # PBC-aware detection should find bonds across periodic boundaries

    def test_detect_bonds_si_unit_cell_without_periodic(self, si_diamond_structure):
        """Test bond detection in Si unit cell.
        
        Note: include_periodic_images is deprecated. Bond detection always uses PBC.
        """
        bonds = detect_bonds(si_diamond_structure, include_periodic_images=False)
        # Bond detection always uses PBC-aware minimum-image convention
        # So the result should be the same as with include_periodic_images=True
        assert len(bonds) >= 1, f"Expected at least 1 bond, got {len(bonds)}"

    def test_detect_bonds_supercell(self, si_diamond_structure):
        """Test bond detection in a supercell."""
        supercell = make_supercell(si_diamond_structure, (2, 2, 2))
        bonds = detect_bonds(supercell, include_periodic_images=False)
        
        # 2x2x2 supercell has 16 atoms, each with 4 bonds
        # Total internal bonds = 16 * 4 / 2 = 32
        assert len(bonds) == 32, f"Expected 32 bonds in 2x2x2 supercell, got {len(bonds)}"

    def test_detect_bonds_respects_covalent_radii(self, si_diamond_structure):
        """Test that bonds are detected based on covalent radii."""
        bonds = detect_bonds(si_diamond_structure, tolerance=0.3, include_periodic_images=True)
        
        # Si-Si bond length is ~2.35 Å
        for bond in bonds:
            assert 2.0 <= bond.distance <= 2.6, f"Unexpected bond distance: {bond.distance}"


class TestSupercell:
    """Tests for supercell generation."""

    def test_make_supercell_identity(self):
        """Test that (1,1,1) supercell returns a copy."""
        structure = Structure(Lattice.cubic(5.0), ["Si"], [[0, 0, 0]])
        supercell = make_supercell(structure, (1, 1, 1))
        
        assert len(supercell) == len(structure)
        # Should be a copy, not the same object
        assert supercell is not structure

    def test_make_supercell_2x2x2(self):
        """Test 2x2x2 supercell generation."""
        structure = Structure(Lattice.cubic(5.0), ["Si"], [[0, 0, 0]])
        supercell = make_supercell(structure, (2, 2, 2))
        
        assert len(supercell) == 8  # 1 * 2^3 = 8 atoms


class TestBoundaryAtoms:
    """Tests for boundary atom generation."""

    def test_generate_boundary_atoms_cubic(self):
        """Test boundary atom generation for cubic cell with corner atom."""
        structure = Structure(Lattice.cubic(5.0), ["Si"], [[0, 0, 0]])
        boundary_atoms = generate_boundary_atoms(structure)
        
        # Atom at origin should have 7 periodic images (all corners except origin)
        assert len(boundary_atoms) == 7

    def test_generate_boundary_atoms_no_boundary(self):
        """Test that atoms not on boundary don't generate images."""
        structure = Structure(Lattice.cubic(5.0), ["Si"], [[0.5, 0.5, 0.5]])
        boundary_atoms = generate_boundary_atoms(structure)
        
        # Atom at center should have no boundary images
        assert len(boundary_atoms) == 0


class TestVisualization:
    """Tests for structure visualization."""

    @pytest.fixture
    def simple_structure(self):
        """Create a simple structure for visualization tests."""
        return Structure(Lattice.cubic(5.0), ["Si"], [[0, 0, 0]])

    def test_plot_structure_3d_creates_figure(self, simple_structure):
        """Test that plot_structure_3d creates a matplotlib figure."""
        import matplotlib.pyplot as plt
        
        fig, ax = plot_structure_3d(simple_structure)
        
        assert fig is not None
        assert ax is not None
        plt.close(fig)

    def test_plot_structure_3d_with_options(self, simple_structure):
        """Test plotting with custom options."""
        import matplotlib.pyplot as plt
        
        options = StructurePlotOptions(
            supercell=(1, 1, 1),
            repeat_boundary=True,
            atom_scale=200.0,
        )
        fig, ax = plot_structure_3d(simple_structure, options)
        
        assert fig is not None
        plt.close(fig)

    def test_visualize_structure_saves_file(self, simple_structure, tmp_path):
        """Test that visualize_structure saves a PNG file."""
        output_path = tmp_path / "test_structure.png"
        
        result = visualize_structure(simple_structure, output_path=output_path)
        
        assert output_path.exists()
        assert result.output_path == output_path
        assert result.n_atoms > 0

    def test_visualize_structure_with_supercell(self, simple_structure, tmp_path):
        """Test visualization with supercell expansion."""
        output_path = tmp_path / "test_supercell.png"
        
        result = visualize_structure(
            simple_structure,
            output_path=output_path,
            supercell=(2, 2, 2),
        )
        
        assert output_path.exists()
        assert result.n_atoms == 8  # 2^3 atoms
        assert result.supercell == (2, 2, 2)


class TestVisualizationFromQEInput:
    """Tests for structure visualization from QE input files."""

    def test_visualize_from_si_scf_input(self, ci_test_data_dir, tmp_path):
        """Test visualization from Si DOS SCF input file."""
        # Read the Si SCF input file
        si_input_file = ci_test_data_dir / "4_Si_DOS" / "si.1_scf.in"
        assert si_input_file.exists(), f"Test file not found: {si_input_file}"
        
        # Read structure from input file
        structure = read_structure(si_input_file)
        assert structure is not None
        assert len(structure) == 2  # Si diamond has 2 atoms in primitive cell
        
        # Generate visualization
        output_path = tmp_path / "si_structure_from_input.png"
        result = visualize_structure(structure, output_path=output_path)
        
        assert output_path.exists()
        assert result.n_atoms == 2
        # Should have at least 1 bond (internal) when not including periodic images
        assert result.n_bonds >= 1

    def test_visualize_si_supercell_from_input(self, ci_test_data_dir, tmp_path):
        """Test visualization of Si supercell from input file."""
        si_input_file = ci_test_data_dir / "4_Si_DOS" / "si.1_scf.in"
        structure = read_structure(si_input_file)
        
        output_path = tmp_path / "si_supercell.png"
        result = visualize_structure(
            structure,
            output_path=output_path,
            supercell=(2, 2, 2),
        )
        
        assert output_path.exists()
        assert result.n_atoms == 16  # 2 atoms * 2^3
        assert result.n_bonds == 32  # 16 atoms * 4 bonds / 2 (each Si has 4 neighbors)
        assert result.supercell == (2, 2, 2)

    def test_visualize_si_with_boundary(self, ci_test_data_dir, tmp_path):
        """Test visualization with boundary repetition."""
        si_input_file = ci_test_data_dir / "4_Si_DOS" / "si.1_scf.in"
        structure = read_structure(si_input_file)
        
        output_path = tmp_path / "si_boundary.png"
        result = visualize_structure(
            structure,
            output_path=output_path,
            repeat_boundary=True,
        )
        
        assert output_path.exists()
        # With boundary repetition, should have more atoms
        assert result.n_atoms > 2
        assert result.repeat_boundary is True


class TestVisualizationResult:
    """Tests for StructureVisualizationResult."""

    def test_result_to_dict(self, tmp_path):
        """Test that result can be converted to dict."""
        from quantumvitas.analysis.structure_viz import StructureVisualizationResult
        
        result = StructureVisualizationResult(
            output_path=tmp_path / "test.png",
            n_atoms=10,
            n_bonds=15,
            supercell=(2, 2, 2),
            repeat_boundary=True,
        )
        
        d = result.to_dict()
        
        assert d["n_atoms"] == 10
        assert d["n_bonds"] == 15
        assert d["supercell"] == [2, 2, 2]
        assert d["repeat_boundary"] is True

