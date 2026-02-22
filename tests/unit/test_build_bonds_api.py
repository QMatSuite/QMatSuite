"""
Unit tests for build_bonds public API.
"""

import pytest
import numpy as np
from qmatsuite.analysis.structure_viz import build_bonds
from pymatgen.core import Structure, Lattice


def test_build_bonds_does_not_require_radii_map():
    """Test that build_bonds does not require radii_map parameter."""
    # Create a simple Si cubic structure
    lattice = Lattice.cubic(5.43)
    structure = Structure(lattice, ["Si", "Si"], [[0, 0, 0], [0.25, 0.25, 0.25]])
    
    # Extract display atoms (simplified - just coordinates and species)
    atoms_cart = np.array([site.coords for site in structure])
    species = [site.specie.symbol for site in structure]
    
    # Call build_bonds without radii_map (should auto-resolve)
    bonds = build_bonds(atoms_cart, species=species)
    
    # Should return a list (possibly empty)
    assert isinstance(bonds, list)
    # Should not raise


def test_build_bonds_with_display_atoms():
    """Test build_bonds with DisplayAtom-like objects."""
    from qmatsuite.analysis.structure_viz import DisplayAtom
    
    # Create mock DisplayAtom objects
    display_atoms = [
        DisplayAtom(
            stable_id="atom_0",
            element="Si",
            cart_coords=np.array([0.0, 0.0, 0.0]),
            frac_coords=np.array([0.0, 0.0, 0.0]),
            original_idx=0,
            translation=(0, 0, 0),
        ),
        DisplayAtom(
            stable_id="atom_1",
            element="Si",
            cart_coords=np.array([1.35, 1.35, 1.35]),
            frac_coords=np.array([0.25, 0.25, 0.25]),
            original_idx=1,
            translation=(0, 0, 0),
        ),
    ]
    
    # Call build_bonds with DisplayAtom list
    bonds = build_bonds(display_atoms)
    
    # Should return a list (possibly empty)
    assert isinstance(bonds, list)
    # Should not raise


def test_build_bonds_fallback_element_does_not_crash():
    """Test that unknown elements do not crash build_bonds."""
    # Create atoms with unknown element
    atoms_cart = np.array([
        [0.0, 0.0, 0.0],
        [2.0, 0.0, 0.0],
    ])
    species = ["Xx", "Yy"]  # Unknown elements
    
    # Should not raise, should return empty list or valid list
    bonds = build_bonds(atoms_cart, species=species)
    
    assert isinstance(bonds, list)
    # May be empty or may have bonds with fallback radius


def test_build_bonds_empty_atoms():
    """Test that build_bonds handles empty atom list."""
    atoms_cart = np.array([]).reshape(0, 3)
    species = []
    
    bonds = build_bonds(atoms_cart, species=species)
    
    assert isinstance(bonds, list)
    assert len(bonds) == 0


def test_build_bonds_malformed_input():
    """Test that build_bonds handles malformed input gracefully."""
    # Invalid input
    bonds = build_bonds([])
    
    assert isinstance(bonds, list)
    # Should not raise
