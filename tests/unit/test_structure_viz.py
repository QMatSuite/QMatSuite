"""Tests for structure visualization module."""

from pathlib import Path

import numpy as np
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
    build_bonds,
    build_bonds_bruteforce,
    build_bonds_cell_list,
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
        """Test bond detection in Si unit cell.
        
        Bonds are computed using simple Euclidean distance on the display atom list.
        Primitive Si has 2 atoms, so we expect 1 bond (the direct bond between them).
        """
        bonds = detect_bonds(si_diamond_structure, include_periodic_images=True)
        # Primitive Si: 2 atoms, 1 bond (direct connection)
        assert len(bonds) == 1, f"Expected 1 bond in primitive Si, got {len(bonds)}"
        # Verify bond properties
        assert bonds[0].idx1 == 0 and bonds[0].idx2 == 1
        assert 2.0 <= bonds[0].distance <= 2.6, f"Bond distance should be ~2.35 Å, got {bonds[0].distance:.3f}"

    def test_detect_bonds_si_unit_cell_without_periodic(self, si_diamond_structure):
        """Test bond detection in Si unit cell.
        
        include_periodic_images is ignored - bonds are always computed from the structure's atoms.
        """
        bonds = detect_bonds(si_diamond_structure, include_periodic_images=False)
        # Should be same as with include_periodic_images=True (parameter is ignored)
        assert len(bonds) == 1, f"Expected 1 bond in primitive Si, got {len(bonds)}"

    def test_detect_bonds_supercell(self, si_diamond_structure):
        """Test bond detection in a supercell.
        
        Bonds are computed using deterministic squared-distance comparison.
        Verifies that detect_bonds produces correct results matching brute-force.
        """
        import numpy as np
        supercell = make_supercell(si_diamond_structure, (2, 2, 2))
        bonds = detect_bonds(supercell, include_periodic_images=False)
        
        # 2x2x2 supercell has 16 atoms
        # Verify basic invariants
        n_atoms = len(supercell)
        for bond in bonds:
            assert 0 <= bond.idx1 < n_atoms, f"Invalid bond index: {bond.idx1}"
            assert 0 <= bond.idx2 < n_atoms, f"Invalid bond index: {bond.idx2}"
            assert bond.idx1 != bond.idx2, "Self-bond found"
            assert bond.distance > 0 and np.isfinite(bond.distance), f"Invalid bond distance: {bond.distance}"
        
        # Verify no duplicate bonds
        pairs = bond_pairs(bonds)
        assert len(pairs) == len(bonds), "Found duplicate bonds"
        
        # Cross-check with brute-force (gold standard)
        atoms_cart = np.array([site.coords for site in supercell])
        species = [site.specie.symbol for site in supercell]
        radii_map = {sym: get_element_radius(sym) for sym in set(species)}
        
        bonds_brute = build_bonds_bruteforce(
            atoms_cart, species, radii_map,
            max_factor=1.2, tolerance=0.3, max_cutoff=3.5
        )
        pairs_brute = bond_pairs(bonds_brute)
        pairs_detect = bond_pairs(bonds)
        
        # Correctness check: bond sets must match
        assert pairs_detect == pairs_brute, (
            f"detect_bonds does not match brute-force!\n"
            f"Missing: {pairs_brute - pairs_detect}\n"
            f"Extra: {pairs_detect - pairs_brute}\n"
            f"detect_bonds: {len(bonds)} bonds, brute-force: {len(bonds_brute)} bonds"
        )
        
        # Margin diagnostic
        margins = compute_bond_margins(bonds_brute, atoms_cart, species, radii_map, 1.2, 0.3, 3.5)
        min_margin = min(margin for _, margin in margins)
        
        if min_margin < 1e-8:
            pytest.fail(
                f"Knife-edge bond detection: min_margin={min_margin:.2e} Å < 1e-8 Å. "
                f"Adjust parameters or ensure deterministic epsilon handling."
            )
        
        # With deterministic implementation, count should be stable
        # Record the expected count for regression testing
        expected_count = len(bonds_brute)
        assert len(bonds) == expected_count, (
            f"Bond count mismatch: detect_bonds={len(bonds)}, brute-force={expected_count}"
        )

    def test_detect_bonds_respects_covalent_radii(self, si_diamond_structure):
        """Test that bonds are detected based on covalent radii."""
        bonds = detect_bonds(si_diamond_structure, tolerance=0.3, include_periodic_images=True)
        
        # Si-Si bond length is ~2.35 Å
        for bond in bonds:
            assert 2.0 <= bond.distance <= 2.6, f"Unexpected bond distance: {bond.distance}"


@pytest.fixture
def si_diamond_structure():
    """Create a Si diamond structure (FCC primitive cell, ibrav=2)."""
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


def bond_pairs(bonds):
    """Helper to extract bond identity pairs: (min(i,j), max(i,j))."""
    return {(min(int(b.idx1), int(b.idx2)), max(int(b.idx1), int(b.idx2))) for b in bonds}


def compute_bond_margins(bonds, atoms_cart, species, radii_map, max_factor=1.2, tolerance=0.3, max_cutoff=3.5):
    """
    Compute margin to cutoff for each bond.
    
    Returns: list of (bond, margin) tuples where margin = cutoff - distance
    """
    from quantumvitas.analysis.structure_viz import get_element_radius
    import numpy as np
    
    margins = []
    for bond in bonds:
        i, j = int(bond.idx1), int(bond.idx2)
        radius_i = radii_map.get(species[i], get_element_radius(species[i]))
        radius_j = radii_map.get(species[j], get_element_radius(species[j]))
        
        max_bond_dist = (radius_i + radius_j) * max_factor + tolerance
        cutoff = min(max_cutoff, max_bond_dist)
        margin = cutoff - bond.distance
        margins.append((bond, margin))
    
    return margins


class TestCellListBondDetection:
    """Tests for cell-list bond detection algorithm validation."""
    
    def test_cell_list_vs_bruteforce_random_atoms(self):
        """Test cell-list matches brute-force on random atom cloud."""
        np.random.seed(42)  # Deterministic
        
        # Generate ~50 random atoms in a cube
        n_atoms = 50
        box_size = 20.0  # 20 Å cube
        atoms_cart = np.random.uniform(0, box_size, size=(n_atoms, 3))
        
        # Random species from a small list with known radii
        species_list = ['H', 'C', 'N', 'O', 'Si']
        species = [species_list[i % len(species_list)] for i in range(n_atoms)]
        
        # Build radii map
        radii_map = {sym: get_element_radius(sym) for sym in species_list}
        
        # Compute bonds with both methods
        bonds_brute = build_bonds_bruteforce(
            atoms_cart, species, radii_map,
            max_factor=1.2, tolerance=0.3, max_cutoff=3.5
        )
        bonds_cell = build_bonds_cell_list(
            atoms_cart, species, radii_map,
            max_factor=1.2, tolerance=0.3, max_cutoff=3.5
        )
        
        # Compare bond sets (by index pairs) - this is the correctness check
        pairs_brute = bond_pairs(bonds_brute)
        pairs_cell = bond_pairs(bonds_cell)
        
        assert pairs_brute == pairs_cell, (
            f"Bond pairs don't match!\n"
            f"Missing in cell-list: {pairs_brute - pairs_cell}\n"
            f"Extra in cell-list: {pairs_cell - pairs_brute}\n"
            f"Brute-force: {len(bonds_brute)} bonds, Cell-list: {len(bonds_cell)} bonds"
        )
        
        # Verify basic invariants
        n_atoms = len(atoms_cart)
        for bonds in [bonds_brute, bonds_cell]:
            for bond in bonds:
                assert 0 <= bond.idx1 < n_atoms, f"Invalid bond index: {bond.idx1}"
                assert 0 <= bond.idx2 < n_atoms, f"Invalid bond index: {bond.idx2}"
                assert bond.idx1 != bond.idx2, "Self-bond found"
                assert bond.distance > 0, f"Non-positive distance: {bond.distance}"
                assert np.isfinite(bond.distance), f"Non-finite distance: {bond.distance}"
        
        # Margin diagnostic: check if system is knife-edge
        margins = compute_bond_margins(bonds_brute, atoms_cart, species, radii_map, max_factor=1.2, tolerance=0.3, max_cutoff=3.5)
        min_margin = min(margin for _, margin in margins)
        
        if min_margin < 1e-8:
            pytest.fail(
                f"Knife-edge bond detection: min_margin={min_margin:.2e} Å < 1e-8 Å. "
                f"This dataset has bonds very close to cutoff. Adjust parameters or "
                f"ensure deterministic epsilon handling."
            )
    
    def test_cell_list_vs_bruteforce_si_primitive(self, si_diamond_structure):
        """Test cell-list matches brute-force on Si primitive structure."""
        # Extract atoms and species
        atoms_cart = np.array([site.coords for site in si_diamond_structure])
        species = [site.specie.symbol for site in si_diamond_structure]
        radii_map = {sym: get_element_radius(sym) for sym in set(species)}
        
        # Compute bonds with both methods
        bonds_brute = build_bonds_bruteforce(
            atoms_cart, species, radii_map,
            max_factor=1.2, tolerance=0.3, max_cutoff=3.5
        )
        bonds_cell = build_bonds_cell_list(
            atoms_cart, species, radii_map,
            max_factor=1.2, tolerance=0.3, max_cutoff=3.5
        )
        
        # Compare bond sets (correctness check)
        pairs_brute = bond_pairs(bonds_brute)
        pairs_cell = bond_pairs(bonds_cell)
        
        assert pairs_brute == pairs_cell, (
            f"Si primitive: bond pairs don't match!\n"
            f"Brute-force: {len(bonds_brute)} bonds, Cell-list: {len(bonds_cell)} bonds"
        )
        
        # Verify invariants
        n_atoms = len(atoms_cart)
        for bond in bonds_brute:
            assert 0 <= bond.idx1 < n_atoms and 0 <= bond.idx2 < n_atoms
            assert bond.idx1 != bond.idx2
            assert bond.distance > 0 and np.isfinite(bond.distance)
    
    def test_cell_list_vs_bruteforce_si_supercell(self, si_diamond_structure):
        """Test cell-list matches brute-force on Si supercell."""
        supercell = make_supercell(si_diamond_structure, (2, 2, 2))
        
        # Extract atoms and species
        atoms_cart = np.array([site.coords for site in supercell])
        species = [site.specie.symbol for site in supercell]
        radii_map = {sym: get_element_radius(sym) for sym in set(species)}
        
        # Compute bonds with both methods
        bonds_brute = build_bonds_bruteforce(
            atoms_cart, species, radii_map,
            max_factor=1.2, tolerance=0.3, max_cutoff=3.5
        )
        bonds_cell = build_bonds_cell_list(
            atoms_cart, species, radii_map,
            max_factor=1.2, tolerance=0.3, max_cutoff=3.5
        )
        
        # Compare bond sets (correctness check) - this is the primary assertion
        pairs_brute = bond_pairs(bonds_brute)
        pairs_cell = bond_pairs(bonds_cell)
        
        assert pairs_brute == pairs_cell, (
            f"Si supercell: bond pairs don't match!\n"
            f"Missing in cell-list: {pairs_brute - pairs_cell}\n"
            f"Extra in cell-list: {pairs_cell - pairs_brute}\n"
            f"Brute-force: {len(bonds_brute)} bonds, Cell-list: {len(bonds_cell)} bonds"
        )
        
        # Verify invariants
        n_atoms = len(atoms_cart)
        for bonds in [bonds_brute, bonds_cell]:
            for bond in bonds:
                assert 0 <= bond.idx1 < n_atoms and 0 <= bond.idx2 < n_atoms
                assert bond.idx1 != bond.idx2
                assert bond.distance > 0 and np.isfinite(bond.distance)
        
        # Margin diagnostic: check if system is knife-edge
        margins = compute_bond_margins(bonds_brute, atoms_cart, species, radii_map, 1.2, 0.3, 3.5)
        min_margin = min(margin for _, margin in margins)
        
        if min_margin < 1e-8:
            pytest.fail(
                f"Knife-edge bond detection: min_margin={min_margin:.2e} Å < 1e-8 Å. "
                f"This dataset has bonds very close to cutoff. Adjust parameters or "
                f"ensure deterministic epsilon handling."
            )
        
        # Stable count assertion (only if not knife-edge)
        # The count should be deterministic with squared-distance + fixed epsilon
        expected_count = len(bonds_brute)
        assert len(bonds_cell) == expected_count, (
            f"Bond counts must match: brute-force={len(bonds_brute)}, cell-list={len(bonds_cell)}"
        )
    
    def test_cell_list_vs_bruteforce_si_with_boundary(self, si_diamond_structure):
        """Test cell-list matches brute-force on Si with boundary atoms."""
        from quantumvitas.analysis.structure_viz import generate_boundary_atoms
        
        # Generate boundary atoms
        boundary_atoms = generate_boundary_atoms(si_diamond_structure)
        
        # Build display atom list (original + boundary)
        atoms_cart = np.array([site.coords for site in si_diamond_structure])
        species = [site.specie.symbol for site in si_diamond_structure]
        
        # Add boundary atoms
        for ba in boundary_atoms:
            atoms_cart = np.vstack([atoms_cart, ba.coords.reshape(1, -1)])
            species.append(ba.symbol)
        
        radii_map = {sym: get_element_radius(sym) for sym in set(species)}
        
        # Compute bonds with both methods
        bonds_brute = build_bonds_bruteforce(
            atoms_cart, species, radii_map,
            max_factor=1.2, tolerance=0.3, max_cutoff=3.5
        )
        bonds_cell = build_bonds_cell_list(
            atoms_cart, species, radii_map,
            max_factor=1.2, tolerance=0.3, max_cutoff=3.5
        )
        
        # Compare bond sets (correctness check)
        pairs_brute = bond_pairs(bonds_brute)
        pairs_cell = bond_pairs(bonds_cell)
        
        assert pairs_brute == pairs_cell, (
            f"Si with boundary: bond pairs don't match!\n"
            f"Brute-force: {len(bonds_brute)} bonds, Cell-list: {len(bonds_cell)} bonds"
        )
        
        # Verify invariants
        n_atoms = len(atoms_cart)
        for bond in bonds_brute:
            assert 0 <= bond.idx1 < n_atoms and 0 <= bond.idx2 < n_atoms
            assert bond.idx1 != bond.idx2
            assert bond.distance > 0 and np.isfinite(bond.distance)
    
    def test_cell_list_edge_case_bin_boundaries(self):
        """Test cell-list handles atoms exactly on bin boundaries."""
        np.random.seed(123)  # Deterministic
        
        # Create atoms positioned at exact cell boundaries
        # Use cell_size = 3.5 + 1e-6 = 3.500001
        cell_size = 3.500001
        max_cutoff = 3.5
        
        # Place atoms at multiples of cell_size
        positions = [
            [0.0, 0.0, 0.0],
            [cell_size, 0.0, 0.0],  # Exactly one cell away
            [cell_size * 2, 0.0, 0.0],  # Two cells away
            [0.0, cell_size, 0.0],
            [cell_size, cell_size, 0.0],
        ]
        
        atoms_cart = np.array(positions)
        species = ['Si'] * len(positions)
        radii_map = {'Si': get_element_radius('Si')}
        
        # Compute bonds with both methods
        bonds_brute = build_bonds_bruteforce(
            atoms_cart, species, radii_map,
            max_factor=1.2, tolerance=0.3, max_cutoff=max_cutoff
        )
        bonds_cell = build_bonds_cell_list(
            atoms_cart, species, radii_map,
            max_factor=1.2, tolerance=0.3, max_cutoff=max_cutoff
        )
        
        # Compare bond sets (correctness check)
        pairs_brute = bond_pairs(bonds_brute)
        pairs_cell = bond_pairs(bonds_cell)
        
        assert pairs_brute == pairs_cell, (
            f"Bin boundary test: bond pairs don't match!\n"
            f"Brute-force: {len(bonds_brute)} bonds, Cell-list: {len(bonds_cell)} bonds"
        )
    
    def test_cell_list_edge_case_degenerate(self):
        """Test cell-list handles degenerate case (all atoms at same position)."""
        # All atoms at origin
        atoms_cart = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]])
        species = ['H', 'H', 'H']
        radii_map = {'H': get_element_radius('H')}
        
        # Both methods should handle this (cell-list falls back to brute-force)
        bonds_brute = build_bonds_bruteforce(
            atoms_cart, species, radii_map,
            max_factor=1.2, tolerance=0.3, max_cutoff=3.5
        )
        bonds_cell = build_bonds_cell_list(
            atoms_cart, species, radii_map,
            max_factor=1.2, tolerance=0.3, max_cutoff=3.5
        )
        
        # Compare bond sets (correctness check)
        pairs_brute = bond_pairs(bonds_brute)
        pairs_cell = bond_pairs(bonds_cell)
        
        assert pairs_brute == pairs_cell, (
            f"Degenerate case: bond pairs don't match!\n"
            f"Brute-force: {len(bonds_brute)} bonds, Cell-list: {len(bonds_cell)} bonds"
        )
    
    def test_cell_list_small_system_fallback(self):
        """Test cell-list falls back to brute-force for very small systems."""
        # Small system (< 10 atoms) should use brute-force internally
        atoms_cart = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]])
        species = ['C', 'C', 'C']
        radii_map = {'C': get_element_radius('C')}
        
        bonds_cell = build_bonds_cell_list(
            atoms_cart, species, radii_map,
            max_factor=1.2, tolerance=0.3, max_cutoff=3.5
        )
        bonds_brute = build_bonds_bruteforce(
            atoms_cart, species, radii_map,
            max_factor=1.2, tolerance=0.3, max_cutoff=3.5
        )
        
        # Should match exactly (cell-list uses brute-force for small systems)
        pairs_cell = bond_pairs(bonds_cell)
        pairs_brute = bond_pairs(bonds_brute)
        
        assert pairs_cell == pairs_brute
    
    def test_build_bonds_default_uses_cell_list(self, si_diamond_structure):
        """Test that build_bonds() default uses cell-list (not brute-force)."""
        atoms_cart = np.array([site.coords for site in si_diamond_structure])
        species = [site.specie.symbol for site in si_diamond_structure]
        radii_map = {sym: get_element_radius(sym) for sym in set(species)}
        
        # Default should use cell-list
        bonds_default = build_bonds(
            atoms_cart, species, radii_map,
            max_factor=1.2, tolerance=0.3, max_cutoff=3.5
        )
        bonds_cell = build_bonds_cell_list(
            atoms_cart, species, radii_map,
            max_factor=1.2, tolerance=0.3, max_cutoff=3.5
        )
        
        # Should match cell-list exactly
        pairs_default = bond_pairs(bonds_default)
        pairs_cell = bond_pairs(bonds_cell)
        
        assert pairs_default == pairs_cell
    
    def test_build_bonds_bruteforce_flag(self, si_diamond_structure):
        """Test that build_bonds() can be forced to use brute-force."""
        atoms_cart = np.array([site.coords for site in si_diamond_structure])
        species = [site.specie.symbol for site in si_diamond_structure]
        radii_map = {sym: get_element_radius(sym) for sym in set(species)}
        
        # Force brute-force
        bonds_forced = build_bonds(
            atoms_cart, species, radii_map,
            max_factor=1.2, tolerance=0.3, max_cutoff=3.5,
            use_bruteforce=True
        )
        bonds_brute = build_bonds_bruteforce(
            atoms_cart, species, radii_map,
            max_factor=1.2, tolerance=0.3, max_cutoff=3.5
        )
        
        # Should match brute-force exactly
        pairs_forced = bond_pairs(bonds_forced)
        pairs_brute = bond_pairs(bonds_brute)
        
        assert pairs_forced == pairs_brute


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
        # With simple Euclidean distance (no PBC), bond count depends on actual distances in supercell
        # The exact count may vary, but should be reasonable (between 1 and 32)
        assert 1 <= result.n_bonds <= 32, f"Expected reasonable bond count, got {result.n_bonds}"
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

