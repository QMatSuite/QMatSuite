"""
3D crystal structure visualization using matplotlib.

This module provides ball-and-stick visualization of crystal structures
with support for supercells and boundary repetition options.

Features:
- Ball-and-stick representation (atoms as spheres, bonds as lines)
- Supercell expansion
- Periodic boundary visualization
- Element-based coloring using CPK-like scheme
- Covalent radius-based bond detection

Functions are reusable from CLI, GUI, or notebooks.
"""

from __future__ import annotations

# Public API exports - _build_bonds is internal-only
__all__ = [
    "visualize_structure",
    "plot_structure_3d",
    "detect_bonds",
    "build_bonds",  # Public API
    "generate_boundary_atoms",
    "make_supercell",
    "get_conventional_cell",
    "canonicalize_structure_in_place",
    "build_display_atoms",
    "StructurePlotOptions",
    "StructureVisualizationResult",
    "Bond",
    "BoundaryAtom",
    "DisplayAtom",
    "DisplayModeParams",
    "get_element_color",
    "get_element_radius",
    "ELEMENT_COLORS",
    "COVALENT_RADII",  # Legacy, deprecated
    "wrap_fractional_coords_shifted",  # Pure shifted-wrap helper
    "WRAP_TOL",  # Wrap tolerance constant
    "BOUNDARY_TOL",  # Boundary tolerance constant
    "BOUNDARY_FRAC_TOL",  # Legacy constant (debug checks only)
    "build_structure_vis_payload",  # Pure transformation: Structure -> visualization payload
]

import matplotlib
matplotlib.use("Agg")  # Headless-safe backend

import numpy as np
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set, Union
from itertools import product
import logging
import os
from collections import defaultdict

import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from pymatgen.core import Structure as PMGStructure
from pymatgen.core.periodic_table import Element
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer

from quantumvitas.analysis.atomic_radii import get_radii_map, get_element_radius as get_radii_element_radius

logger = logging.getLogger(__name__)


# =============================================================================
# CPK-like element colors (simplified palette)
# =============================================================================

ELEMENT_COLORS: Dict[str, str] = {
    # Common elements with distinctive colors
    "H": "#FFFFFF",   # White
    "C": "#333333",   # Dark gray
    "N": "#3050F8",   # Blue
    "O": "#FF0D0D",   # Red
    "F": "#90E050",   # Light green
    "S": "#FFFF30",   # Yellow
    "P": "#FF8000",   # Orange
    "Cl": "#1FF01F",  # Green
    "Br": "#A62929",  # Dark red
    "I": "#940094",   # Purple
    # Metals
    "Na": "#AB5CF2",  # Violet
    "K": "#8F40D4",   # Purple
    "Mg": "#8AFF00",  # Light green
    "Ca": "#3DFF00",  # Lime
    "Fe": "#E06633",  # Brown-orange
    "Cu": "#C88033",  # Copper
    "Zn": "#7D80B0",  # Gray-blue
    "Ag": "#C0C0C0",  # Silver
    "Au": "#FFD123",  # Gold
    "Al": "#BFA6A6",  # Light gray
    # Semiconductors
    "Si": "#F0C8A0",  # Tan/beige
    "Ge": "#668F8F",  # Gray-green
    "Ga": "#C28F8F",  # Pink-gray
    "As": "#BD80E3",  # Purple
    # Transition metals
    "Ti": "#BFC2C7",  # Silver
    "V": "#A6A6AB",   # Gray
    "Cr": "#8A99C7",  # Blue-gray
    "Mn": "#9C7AC7",  # Purple-gray
    "Co": "#F090A0",  # Pink
    "Ni": "#50D050",  # Green
    # Lanthanides/actinides (generic)
    "La": "#70D4FF",  # Light blue
    "U": "#008FFF",   # Blue
    # Default
    "_default": "#FF1493",  # Deep pink for unknown elements
}


def get_element_color(symbol: str) -> str:
    """Get color for an element symbol."""
    return ELEMENT_COLORS.get(symbol, ELEMENT_COLORS["_default"])


# Legacy: Keep COVALENT_RADII for backward compatibility (deprecated, use atomic_radii module)
# Imported from atomic_radii for compatibility
from quantumvitas.analysis.atomic_radii import DEFAULT_COVALENT_RADII as COVALENT_RADII


def get_element_radius(symbol: str) -> float:
    """
    Get covalent radius for an element in Angstroms.
    
    DEPRECATED: Use quantumvitas.analysis.atomic_radii.get_element_radius() instead.
    Kept for backward compatibility.
    """
    return get_radii_element_radius(symbol, fallback_radius=1.0)


# =============================================================================
# Wrapping and coordinate utilities
# =============================================================================

# Tolerance constants for coordinate handling
# 
# wrap_tol: Controls the shifted canonical interval [lo, lo+1) where lo = -wrap_tol.
#           Used for representative selection (integer lattice translations only).
#           Default 1e-4 means canonical interval is [-1e-4, 0.9999).
# 
# boundary_tol: Used only for boundary-repeat near-face tests (not for geometry modification).
#               Default 0.01 means atoms within 0.01 of boundaries generate images.
#               In supercell mode, this is scaled per dimension by supercell factors.
#
# BOUNDARY_FRAC_TOL: Legacy constant (1e-6). No longer used for geometry modifications.
#                    May be used for debug consistency checks (atol) only.

# Default wrap tolerance for canonicalization (representative selection interval)
WRAP_TOL = 1e-4

# Default boundary tolerance for boundary-repeat detection (not for geometry modification)
BOUNDARY_TOL = 0.01

# Legacy constant - no longer used for geometry modifications, only for debug checks
BOUNDARY_FRAC_TOL = 1e-6


# =============================================================================
# Canonicalization Contract
# =============================================================================
#
# CRITICAL DESIGN RULE: Single-Point Canonicalization
#
# Fractional coordinates are canonicalized exactly once at the entry point of
# the visualization pipeline, never again downstream.
#
# Allowed call sites for canonicalize_structure_in_place():
# - build_display_atoms() - main entry for GUI visualization
# - visualize_structure() - high-level API entry point (canonicalizes once, passes to plot_structure_3d)
# NOTE: plot_structure_3d() accepts optional pre-canonicalized structure to avoid double canonicalization
#
# FORBIDDEN: Internal helpers MUST NOT canonicalize:
# - detect_bonds() - must assume input is already canonicalized (pure geometric function)
# - make_supercell() - must assume input is already canonicalized
# - generate_boundary_atoms() - must assume input is already canonicalized
# - build_bonds() / build_bonds_bruteforce() / build_bonds_cell_list() - pure geometric functions, no canonicalization
#
# canonicalize_frac_coords() may ONLY be called:
# - Inside canonicalize_structure_in_place() (the only allowed caller)
# - Inside wrap_fractional_coords() (which is a thin wrapper for backward compatibility)
#
# This contract ensures:
# - Deterministic, stable bond counts across small coordinate shifts
# - No double-canonicalization that could fold boundary images back into the main cell
# - Clear separation: canonicalization is pre-processing, not geometry logic
# - Bond detection functions are pure: they consume prepared geometry, never modify it
#
# IMPORTANT NOTES:
# - Canonicalization uses pure shifted wrap (representative selection only):
#   * No snapping, rounding, or threshold-based geometry modifications
#   * Only integer lattice translations (geometry-preserving)
#   * Canonical interval is [lo, lo+1) where lo = -WRAP_TOL (default [-1e-4, 0.9999))
# - Boundary repeat uses BOUNDARY_TOL (default 0.01) for near-face detection:
#   * In supercell mode, tolerance is scaled per dimension: tol_dim = boundary_tol / factor
#   * This ensures real-space thickness is approximately invariant vs supercell size
#   * Uses geometric distances to lo/hi boundaries (not abs(f-0)/abs(f-1))
# - BOUNDARY_FRAC_TOL (1e-6) is legacy and only used for debug consistency checks (atol)
# - See docs/CANONICALIZATION_DESIGN.md for detailed documentation.
#
# =============================================================================


def canonicalize_structure_in_place(
    structure: PMGStructure,
    wrap_tol: float = WRAP_TOL,
) -> None:
    """
    Canonicalize the fractional coordinates of a pymatgen Structure in place,
    using canonicalize_frac_coords() exactly once on the primitive structure.
    
    CRITICAL: This is the ONLY place we should wrap fractional coordinates.
    After this, all downstream operations (supercell construction, boundary-image
    generation, bond detection) operate on these already-canonicalized coordinates
    without further canonicalization.
    
    Canonicalization is representative selection only: it uses pure shifted wrap
    (integer lattice translations) to bring coordinates into [lo, lo+1) where lo = -wrap_tol.
    No snapping, rounding, or threshold-based geometry modifications are applied.
    
    IMPORTANT USAGE RULES:
    - This function is called ONLY at entry points:
      * build_display_atoms() - main entry for GUI visualization
      * visualize_structure() - high-level API entry point
      * plot_structure_3d() - matplotlib visualization entry point
    - NEVER call this from:
      * detect_bonds() or any bond detection function
      * make_supercell() or generate_boundary_atoms()
      * Any other internal helper
    
    The canonicalization ensures:
    - Representative selection via integer lattice translations (geometry-preserving)
    - Consistent supercell construction (coordinates in canonical interval)
    - Correct boundary atom generation (base atoms canonicalized, images not)
    
    Args:
        structure: pymatgen Structure to canonicalize (modified in place)
        wrap_tol: Wrap tolerance controlling canonical interval (defaults to WRAP_TOL = 1e-4)
                  Canonical interval is [-wrap_tol, 1 - wrap_tol)
    
    See Also:
        canonicalize_frac_coords() - Core canonicalization logic (pure shifted wrap)
        docs/CANONICALIZATION_DESIGN.md - Detailed documentation
    """
    for i, site in enumerate(structure):
        frac = np.array(site.frac_coords)
        frac_canon = canonicalize_frac_coords(frac, wrap_tol=wrap_tol)
        # Update the site's fractional coordinates
        structure.replace(i, site.specie, frac_canon, coords_are_cartesian=False)


def canonicalize_frac_coords(
    frac: np.ndarray,
    wrap_tol: float = WRAP_TOL,
) -> np.ndarray:
    """
    Canonicalize fractional coordinates using pure shifted wrap (representative selection only).
    
    This function performs representative selection: it adds/subtracts integers to bring
    coordinates into the canonical interval [lo, lo+1) where lo = -wrap_tol.
    It does NOT snap, round, or apply threshold-based geometry modifications.
    
    IMPORTANT: This function is the core canonicalization logic. It is called
    ONLY from canonicalize_structure_in_place() (and wrap_fractional_coords() wrapper).
    Never call this directly from bond detection or geometry helpers.

    Algorithm:
    - Pure shifted wrap: (f - lo) - floor(f - lo) + lo
    - This ensures coordinates are in [lo, lo+1) where lo = -wrap_tol
    - No snapping, rounding, or threshold-based modifications
    - Only integer lattice translations (geometry-preserving)

    Args:
        frac: Fractional coordinates (can be shape (N, 3) or (3,))
        wrap_tol: Wrap tolerance controlling canonical interval (defaults to WRAP_TOL = 1e-4)
                  Canonical interval is [-wrap_tol, 1 - wrap_tol)

    Returns:
        Canonicalized fractional coordinates in [lo, lo+1) where lo = -wrap_tol, as a fresh array

    See Also:
        canonicalize_structure_in_place() - Entry point that calls this function
        wrap_fractional_coords_shifted() - Pure wrap implementation
        docs/CANONICALIZATION_DESIGN.md - Detailed documentation
    """
    # Use the pure shifted wrap helper (no snapping)
    return wrap_fractional_coords_shifted(frac, wrap_tol=wrap_tol)


def wrap_fractional_coords(frac: np.ndarray, wrap_tol: float = WRAP_TOL) -> np.ndarray:
    """
    Wrap fractional coordinates using pure shifted wrap (backward compatibility wrapper).
    
    This is a thin wrapper around canonicalize_frac_coords for backward compatibility.
    It uses pure shifted wrap (no snapping) to bring coordinates into [lo, lo+1) where lo = -wrap_tol.
    
    Args:
        frac: Fractional coordinates (can be 1D or 2D array)
        wrap_tol: Wrap tolerance controlling canonical interval (defaults to WRAP_TOL = 1e-4)
        
    Returns:
        Wrapped fractional coordinates in [lo, lo+1) where lo = -wrap_tol
    """
    return canonicalize_frac_coords(frac, wrap_tol=wrap_tol)


def wrap_fractional_coords_shifted(
    frac: np.ndarray,
    wrap_tol: float = 0.0,
) -> np.ndarray:
    """
    Wrap fractional coordinates to [lo, lo+1) where lo = -wrap_tol.
    
    This is a representative selection only: it adds/subtracts integers to bring
    coordinates into the target range. It does not change geometry except by
    lattice translations (which are equivalent in periodic systems).
    
    Unlike canonicalize_frac_coords(), this function does NOT snap, round, or
    apply threshold-based nudging. It only performs modulo wrapping with a shift.
    
    Args:
        frac: Fractional coordinates (can be 1D or 2D array)
        wrap_tol: Lower bound for wrapping range (default 0.0 gives [0, 1))
        
    Returns:
        Wrapped fractional coordinates in [lo, lo+1) where lo = -wrap_tol
    """
    frac = np.asarray(frac)
    was_1d = frac.ndim == 1
    if was_1d:
        frac = frac.reshape(1, -1)
    
    lo = -wrap_tol
    # Shift by lo, apply floor to get integer part, subtract to wrap
    result = frac - lo
    result = result - np.floor(result) + lo
    
    if was_1d:
        result = result.reshape(-1)
    
    return result


def wrap_cartesian_coords(
    coords: np.ndarray,
    lattice,
    wrap_tol: float = WRAP_TOL,
) -> np.ndarray:
    """
    Wrap Cartesian coordinates into the unit cell.
    
    Converts to fractional, wraps using pure shifted wrap, then back to Cartesian.
    
    Args:
        coords: Cartesian coordinates (can be 1D or 2D array)
        lattice: pymatgen Lattice object
        wrap_tol: Wrap tolerance controlling canonical interval (defaults to WRAP_TOL = 1e-4)
        
    Returns:
        Wrapped Cartesian coordinates
    """
    coords = np.asarray(coords)
    was_1d = coords.ndim == 1
    if was_1d:
        coords = coords.reshape(1, -1)
    
    # Convert to fractional
    frac = np.array([lattice.get_fractional_coords(c) for c in coords])
    
    # Wrap using pure shifted wrap (no snapping)
    frac_wrapped = wrap_fractional_coords(frac, wrap_tol=wrap_tol)
    
    # Convert back to Cartesian
    cart_wrapped = np.array([lattice.get_cartesian_coords(f) for f in frac_wrapped])
    
    if was_1d:
        cart_wrapped = cart_wrapped.reshape(-1)
    
    return cart_wrapped


# =============================================================================
# Utility functions
# =============================================================================

def _normalize_supercell(value: Any) -> Tuple[int, int, int]:
    """
    Normalize supercell input to tuple of three integers.
    
    Accepts:
    - Tuple[int, int, int]: returned as-is
    - int: converted to (n, n, n)
    - List[int]: converted to tuple
    
    Args:
        value: Supercell specification
        
    Returns:
        Tuple of (a, b, c) scaling factors
    """
    if isinstance(value, int):
        return (value, value, value)
    elif isinstance(value, (tuple, list)):
        if len(value) != 3:
            raise ValueError(f"Supercell must be 3 elements, got {len(value)}")
        return tuple(int(v) for v in value)
    else:
        raise TypeError(f"Supercell must be int or tuple/list of 3 ints, got {type(value)}")


# =============================================================================
# Bond detection - SINGLE SOURCE OF TRUTH
# =============================================================================
#
# Bond detection contract:
# - Bond detection functions (detect_bonds, build_bonds, build_bonds_bruteforce,
#   build_bonds_cell_list) must be pure geometric functions:
#   given a fixed geometry (atom positions) and cutoff parameters, they return
#   the same set of bonds deterministically.
# - They MUST NOT canonicalize or wrap coordinates. Geometry preparation
#   (canonicalization, supercells, boundary images) is done BEFORE calling them.
# - All canonicalization happens once at the primitive input via
#   canonicalize_structure_in_place() at entry points (build_display_atoms,
#   visualize_structure, plot_structure_3d).
# - After canonicalization, supercells and boundary images are built via integer
#   lattice translations only (no further canonicalization).
# - Bond detection then operates on the prepared geometry as-is.
#
# =============================================================================

@dataclass
class Bond:
    """Represents a bond between two atoms."""
    idx1: int  # Index of first atom
    idx2: int  # Index of second atom
    coord1: np.ndarray  # Coordinates of first atom
    coord2: np.ndarray  # Coordinates of second atom
    distance: float


# Constants for cell-list algorithm
CELL_LIST_EPS = 1e-6  # Epsilon for r_cut safety margin
CELL_LIST_DIST_EPS = 1e-9  # Epsilon for distance comparison to avoid float boundary misses


def build_bonds_bruteforce(
    atoms_cart: np.ndarray,
    species: List[str],
    radii_map: Dict[str, float],
    *,
    max_factor: float = 1.2,
    tolerance: float = 0.3,
    max_cutoff: float = 3.5,
) -> List[Bond]:
    """
    Gold standard brute-force O(N²) bond detection.
    
    This is the reference implementation that produces exact results.
    Used for testing and validation of accelerated algorithms.
    
    PRECONDITION: This is a pure geometric function. The input atom positions
    (atoms_cart) must already be prepared (canonicalized if needed, supercell
    expanded if needed, boundary images added if needed). This function does NOT
    canonicalize, wrap, or modify coordinates. It simply computes Euclidean
    distances and returns bonds based on the provided geometry.
    
    Bond criterion: distance <= min(max_cutoff, (r_i + r_j) * max_factor + tolerance)
    
    Args:
        atoms_cart: Array of shape (N, 3) with Cartesian coordinates (display atoms)
        species: List of N element symbols (matching display atoms)
        radii_map: Dictionary mapping element symbols to radii
        max_factor: Multiplier for sum of radii (default 1.2)
        tolerance: Extra tolerance in Å (default 0.3)
        max_cutoff: Maximum distance to consider in Å (default 3.5)
        
    Returns:
        List of Bond objects with idx1 < idx2 (no duplicates, deterministic order)
    """
    atoms_cart = np.asarray(atoms_cart)
    n_atoms = len(atoms_cart)
    
    if n_atoms == 0:
        return []
    
    if len(species) != n_atoms:
        raise ValueError(f"species list length ({len(species)}) must match atoms_cart length ({n_atoms})")
    
    bonds: List[Bond] = []
    
    # Brute-force O(N²) distance check
    for i in range(n_atoms):
        coord_i = atoms_cart[i]
        elem_i = species[i]
        radius_i = radii_map.get(elem_i, 1.0)
        
        for j in range(i + 1, n_atoms):  # j > i ensures no duplicates
            coord_j = atoms_cart[j]
            elem_j = species[j]
            radius_j = radii_map.get(elem_j, 1.0)
            
            # Euclidean distance
            dist = np.linalg.norm(coord_j - coord_i)
            
            # Bond criterion: distance <= min(max_cutoff, (r_i + r_j) * max_factor + tolerance)
            max_bond_dist = (radius_i + radius_j) * max_factor + tolerance
            threshold = min(max_cutoff, max_bond_dist)
            
            if dist <= threshold:
                bonds.append(Bond(
                    idx1=i,
                    idx2=j,
                    coord1=coord_i.copy(),
                    coord2=coord_j.copy(),
                    distance=float(dist),
                ))
    
    return bonds


def build_bonds_cell_list(
    atoms_cart: np.ndarray,
    species: List[str],
    radii_map: Dict[str, float],
    *,
    max_factor: float = 1.2,
    tolerance: float = 0.3,
    max_cutoff: float = 3.5,
) -> List[Bond]:
    """
    Accelerated cell-list (neighbor-grid) bond detection.
    
    Produces identical results to brute-force but with O(N) average case complexity
    for sparse systems. Guaranteed to match brute-force results exactly.
    
    PRECONDITION: This is a pure geometric function. The input atom positions
    (atoms_cart) must already be prepared (canonicalized if needed, supercell
    expanded if needed, boundary images added if needed). This function does NOT
    canonicalize, wrap, or modify coordinates. It simply computes Euclidean
    distances using a cell-list acceleration and returns bonds based on the
    provided geometry.
    
    Algorithm:
    1. Compute safe global cutoff: r_cut = max_cutoff + eps
    2. Use cell_size = r_cut (ensures only 27 neighbor cells needed)
    3. Build grid keyed by integer cell indices
    4. For each atom, only check neighbors in same cell + 26 adjacent cells
    5. Use i<j discipline to avoid duplicates
    
    Bond criterion: distance <= min(max_cutoff, (r_i + r_j) * max_factor + tolerance)
    
    Args:
        atoms_cart: Array of shape (N, 3) with Cartesian coordinates (display atoms)
        species: List of N element symbols (matching display atoms)
        radii_map: Dictionary mapping element symbols to radii
        max_factor: Multiplier for sum of radii (default 1.2)
        tolerance: Extra tolerance in Å (default 0.3)
        max_cutoff: Maximum distance to consider in Å (default 3.5)
        
    Returns:
        List of Bond objects with idx1 < idx2 (no duplicates, deterministic order)
    """
    atoms_cart = np.asarray(atoms_cart)
    n_atoms = len(atoms_cart)
    
    if n_atoms == 0:
        return []
    
    if len(species) != n_atoms:
        raise ValueError(f"species list length ({len(species)}) must match atoms_cart length ({n_atoms})")
    
    # For very small systems, brute-force is faster
    if n_atoms < 10:
        return build_bonds_bruteforce(atoms_cart, species, radii_map, max_factor=max_factor, tolerance=tolerance, max_cutoff=max_cutoff)
    
    # Compute safe global cutoff: r_cut = max_cutoff + eps
    # This ensures any possible bond has distance <= r_cut
    r_cut = max_cutoff + CELL_LIST_EPS
    cell_size = r_cut  # Critical: cell_size = r_cut ensures only 27 neighbor cells needed
    
    # Find bounding box to choose origin (avoid negative/float issues)
    xmin, ymin, zmin = atoms_cart.min(axis=0)
    xmax, ymax, zmax = atoms_cart.max(axis=0)
    
    # Handle edge case: all atoms at same position
    if xmax - xmin < 1e-10 and ymax - ymin < 1e-10 and zmax - zmin < 1e-10:
        # Fall back to brute-force for degenerate case
        return build_bonds_bruteforce(atoms_cart, species, radii_map, max_factor=max_factor, tolerance=tolerance, max_cutoff=max_cutoff)
    
    # Build cell grid: map (ix, iy, iz) -> list of atom indices
    cell_grid: Dict[Tuple[int, int, int], List[int]] = defaultdict(list)
    
    for i in range(n_atoms):
        x, y, z = atoms_cart[i]
        # Compute cell indices using floor (handles negative correctly)
        ix = int(np.floor((x - xmin) / cell_size))
        iy = int(np.floor((y - ymin) / cell_size))
        iz = int(np.floor((z - zmin) / cell_size))
        cell_grid[(ix, iy, iz)].append(i)
    
    bonds: List[Bond] = []
    
    # For each cell, check atoms with neighbors in same cell + 26 adjacent cells
    # Use i<j discipline to avoid duplicates
    for (ix, iy, iz), atoms_in_cell in cell_grid.items():
        # Check all 27 cells: current cell + 26 neighbors (3×3×3 grid)
        for dix in [-1, 0, 1]:
            for diy in [-1, 0, 1]:
                for diz in [-1, 0, 1]:
                    neighbor_cell = (ix + dix, iy + diy, iz + diz)
                    neighbor_atoms = cell_grid.get(neighbor_cell, [])
                    
                    # For each atom in current cell
                    for i in atoms_in_cell:
                        coord_i = atoms_cart[i]
                        elem_i = species[i]
                        radius_i = radii_map.get(elem_i, 1.0)
                        
                        # Check against atoms in neighbor cell
                        # Use i<j to avoid duplicates (ensures each pair checked exactly once)
                        for j in neighbor_atoms:
                            if i >= j:  # Skip self and already-checked pairs
                                continue
                            
                            coord_j = atoms_cart[j]
                            elem_j = species[j]
                            radius_j = radii_map.get(elem_j, 1.0)
                            
                            # Euclidean distance
                            dist = np.linalg.norm(coord_j - coord_i)
                            
                            # Bond criterion with small epsilon for float boundary safety
                            max_bond_dist = (radius_i + radius_j) * max_factor + tolerance
                            threshold = min(max_cutoff, max_bond_dist) + CELL_LIST_DIST_EPS
                            
                            if dist <= threshold:
                                bonds.append(Bond(
                                    idx1=i,
                                    idx2=j,
                                    coord1=coord_i.copy(),
                                    coord2=coord_j.copy(),
                                    distance=float(dist),
                                ))
    
    # Sort bonds to ensure deterministic ordering (by idx1, then idx2)
    bonds.sort(key=lambda b: (b.idx1, b.idx2))
    
    return bonds


def _build_bonds(
    atoms_cart: np.ndarray,
    species: List[str],
    radii_map: Dict[str, float],
    *,
    max_factor: float = 1.2,
    tolerance: float = 0.3,
    max_cutoff: float = 3.5,
    use_bruteforce: bool = False,  # Debug option to force brute-force
) -> List[Bond]:
    """
    INTERNAL pure algorithm for bond construction.
    
    This is the internal implementation that requires radii_map explicitly.
    Do NOT call this directly from outside this module. Use build_bonds() instead.
    
    PRECONDITION: This is a pure geometric function. The input atom positions
    (atoms_cart) must already be prepared (canonicalized if needed, supercell
    expanded if needed, boundary images added if needed). This function does NOT
    canonicalize, wrap, or modify coordinates. It simply computes bonds based on
    the provided geometry.
    
    Bond criterion: distance <= min(max_cutoff, (r_i + r_j) * max_factor + tolerance)
    
    Args:
        atoms_cart: Array of shape (N, 3) with Cartesian coordinates (display atoms)
        species: List of N element symbols (matching display atoms)
        radii_map: Dictionary mapping element symbols to radii (REQUIRED)
        max_factor: Multiplier for sum of radii (default 1.2)
        tolerance: Extra tolerance in Å (default 0.3)
        max_cutoff: Maximum distance to consider in Å (default 3.5)
        use_bruteforce: If True, use brute-force algorithm (for debugging/testing)
        
    Returns:
        List of Bond objects with idx1 < idx2 (no duplicates, deterministic order)
    """
    # Check for debug validation flag
    debug_validate = os.environ.get('QV_DEBUG_BONDS_VALIDATE', '0') == '1'
    
    if use_bruteforce or debug_validate:
        bonds_brute = build_bonds_bruteforce(
            atoms_cart, species, radii_map,
            max_factor=max_factor, tolerance=tolerance, max_cutoff=max_cutoff
        )
        
        if debug_validate:
            # Cross-check with cell-list
            bonds_cell = build_bonds_cell_list(
                atoms_cart, species, radii_map,
                max_factor=max_factor, tolerance=tolerance, max_cutoff=max_cutoff
            )
            
            # Compare bond sets (by index pairs)
            pairs_brute = set((b.idx1, b.idx2) for b in bonds_brute)
            pairs_cell = set((b.idx1, b.idx2) for b in bonds_cell)
            
            if pairs_brute != pairs_cell:
                missing_in_cell = pairs_brute - pairs_cell
                extra_in_cell = pairs_cell - pairs_brute
                error_msg = (
                    f"Bond validation failed: cell-list does not match brute-force!\n"
                    f"Missing in cell-list: {missing_in_cell}\n"
                    f"Extra in cell-list: {extra_in_cell}\n"
                    f"Brute-force bonds: {len(bonds_brute)}, Cell-list bonds: {len(bonds_cell)}"
                )
                logger.error(error_msg)
                raise AssertionError(error_msg)
            
            # Also check distances match (within tolerance)
            dist_map_brute = {(b.idx1, b.idx2): b.distance for b in bonds_brute}
            dist_map_cell = {(b.idx1, b.idx2): b.distance for b in bonds_cell}
            
            for pair in pairs_brute:
                dist_brute = dist_map_brute[pair]
                dist_cell = dist_map_cell[pair]
                if abs(dist_brute - dist_cell) > 1e-6:
                    error_msg = (
                        f"Bond distance mismatch for pair {pair}: "
                        f"brute-force={dist_brute}, cell-list={dist_cell}, diff={abs(dist_brute - dist_cell)}"
                    )
                    logger.error(error_msg)
                    raise AssertionError(error_msg)
            
            logger.debug(f"Bond validation passed: {len(bonds_brute)} bonds match exactly")
        
        return bonds_brute
    
    # Default: use cell-list algorithm
    return build_bonds_cell_list(
        atoms_cart, species, radii_map,
        max_factor=max_factor, tolerance=tolerance, max_cutoff=max_cutoff
    )


def build_bonds(
    display_atoms: Union[List[Any], np.ndarray],
    lattice: Optional[Any] = None,
    *,
    radii_policy: str = "covalent",
    fallback_radius: float = 1.2,
    max_factor: float = 1.2,
    tolerance: float = 0.3,
    max_cutoff: float = 3.5,
    use_bruteforce: bool = False,
    **kwargs,  # Ignore other kwargs for compatibility
) -> List[Bond]:
    """
    PUBLIC API for bond construction - single source of truth.
    
    This is the ONLY function that should be called from outside this module.
    It automatically resolves radii_map and applies fallback rules.
    
    Args:
        display_atoms: List of DisplayAtom objects OR array of (N, 3) coordinates
        lattice: Optional lattice (for compatibility, not used in bond calculation)
        radii_policy: Radii policy (default: "covalent")
        fallback_radius: Default radius for unknown elements in Angstroms (default: 1.2)
        max_factor: Multiplier for sum of radii (default 1.2)
        tolerance: Extra tolerance in Å (default 0.3)
        max_cutoff: Maximum distance to consider in Å (default 3.5)
        use_bruteforce: If True, use brute-force algorithm (for debugging/testing)
        **kwargs: May contain 'species' if display_atoms is an array
        
    Returns:
        List of Bond objects with idx1 < idx2 (no duplicates, deterministic order)
        Returns empty list on any error (never raises)
    """
    try:
        # Handle different input formats
        if isinstance(display_atoms, np.ndarray):
            # Array of coordinates - need species separately
            if 'species' not in kwargs:
                logger.warning("build_bonds: atoms_cart array provided but 'species' not found, returning empty bonds")
                return []
            atoms_cart = display_atoms
            species = kwargs['species']
        elif hasattr(display_atoms, '__iter__') and len(display_atoms) > 0:
            # List of DisplayAtom objects (check for DisplayAtom attributes)
            first = display_atoms[0]
            if hasattr(first, 'cart_coords') and hasattr(first, 'element'):
                # DisplayAtom objects
                atoms_cart = np.array([atom.cart_coords for atom in display_atoms])
                species = [atom.element for atom in display_atoms]
            elif hasattr(first, 'coords') and hasattr(first, 'symbol'):
                # Alternative DisplayAtom format
                atoms_cart = np.array([atom.coords for atom in display_atoms])
                species = [atom.symbol for atom in display_atoms]
            else:
                logger.warning(f"build_bonds: unrecognized display_atoms format, returning empty bonds")
                return []
        else:
            logger.warning(f"build_bonds: empty or invalid display_atoms, returning empty bonds")
            return []
        
        # Get base radii map
        radii_map = get_radii_map(policy=radii_policy, fallback_radius=fallback_radius)
        
        # Build radii map for species with fallback
        missing_elements = set()
        final_radii_map = {}
        for sym in set(species):
            if sym in radii_map:
                final_radii_map[sym] = radii_map[sym]
            else:
                final_radii_map[sym] = fallback_radius
                if sym not in missing_elements:
                    missing_elements.add(sym)
                    logger.warning(f"Unknown element '{sym}' not in radii table, using fallback radius {fallback_radius} Å")
        
        # If radii_map is malformed or empty, return empty bonds
        if not final_radii_map:
            logger.warning("Empty radii_map, returning no bonds")
            return []
        
        # Call internal function
        return _build_bonds(
            atoms_cart,
            species,
            final_radii_map,
            max_factor=max_factor,
            tolerance=tolerance,
            max_cutoff=max_cutoff,
            use_bruteforce=use_bruteforce,
        )
    except Exception as e:
        logger.warning(f"Bond building failed: {e}, returning empty bonds")
        return []


def build_bonds_cartesian(
    atoms_cart: np.ndarray,
    species: List[str],
    radii_map: Dict[str, float],
    *,
    max_factor: float = 1.2,
    tolerance: float = 0.3,
    max_cutoff: float = 3.5,
    use_bruteforce: bool = False,
) -> List[Bond]:
    """
    LEGACY function for unit tests - direct cartesian bond building.
    
    This function is provided for backward compatibility with unit tests that
    call build_bonds with raw arrays (atoms_cart, species, radii_map).
    
    **DO NOT use this in production code.** Use build_bonds() with DisplayAtom
    objects instead.
    
    Args:
        atoms_cart: Array of shape (N, 3) with Cartesian coordinates
        species: List of N element symbols
        radii_map: Dictionary mapping element symbols to radii
        max_factor: Multiplier for sum of radii (default 1.2)
        tolerance: Extra tolerance in Å (default 0.3)
        max_cutoff: Maximum distance to consider in Å (default 3.5)
        use_bruteforce: If True, use brute-force algorithm (for debugging/testing)
        
    Returns:
        List of Bond objects
    """
    return _build_bonds(
        atoms_cart, species, radii_map,
        max_factor=max_factor, tolerance=tolerance, max_cutoff=max_cutoff,
        use_bruteforce=use_bruteforce
    )


# Legacy function for backward compatibility
def detect_bonds(
    structure: PMGStructure,
    tolerance: float = 0.3,
    max_cutoff: float = 3.5,
    include_periodic_images: bool = True,  # Ignored, kept for compatibility
) -> List[Bond]:
    """
    Detect bonds in a structure using the cell-list neighbor search.
    
    This function is kept for backward compatibility but now uses build_bonds
    internally. For new code, use build_bonds directly.
    
    PRECONDITIONS (pure geometric function):
    - The input structure geometry (primitive or supercell) MUST already be prepared:
      * If it started as a primitive, its fractional coordinates have already
        been canonicalized once via canonicalize_structure_in_place() at an entry point.
      * Any supercells or boundary-image atoms were built on top of that
        canonicalized primitive via integer lattice translations only (no further canonicalization).
    - This function MUST NOT canonicalize or wrap coordinates. It simply
      uses the given positions to find neighbors and returns unique bonds.
    - Geometry preparation (canonicalization, supercells, boundary images) is done
      BEFORE calling this function. This function only consumes the prepared geometry.
    
    .. deprecated:: 
        The `include_periodic_images` parameter is ignored. Bonds are computed
        using simple Euclidean distance on the provided structure's atoms.
        For periodic behavior, use display modes (supercell, boundary repeat)
        to generate the appropriate atom list before calling this function.
    
    Args:
        structure: pymatgen Structure object (MUST be already prepared/canonicalized)
        tolerance: Extra tolerance for bond detection (Å)
        max_cutoff: Maximum distance to consider (Å)
        include_periodic_images: Ignored (kept for backward compatibility)
        
    Returns:
        List of Bond objects computed from structure's atoms using Euclidean distance
    """
    # Extract atoms and species (structure is assumed to be already canonicalized)
    atoms_cart = np.array([site.coords for site in structure])
    species = [site.specie.symbol for site in structure]
    
    # Use public API (auto-resolves radii_map)
    return build_bonds(
        atoms_cart,
        species=species,
        tolerance=tolerance,
        max_cutoff=max_cutoff,
    )


# =============================================================================
# Boundary repetition
# =============================================================================

@dataclass
class BoundaryAtom:
    """An atom repeated at a boundary position."""
    original_idx: int  # Index of original atom
    coords: np.ndarray  # Cartesian coordinates
    frac_coords: np.ndarray  # Fractional coordinates
    symbol: str


def generate_boundary_atoms(
    structure: PMGStructure,
    boundary_tol: float = BOUNDARY_TOL,
    wrap_tol: float = WRAP_TOL,
    supercell_factors: Tuple[int, int, int] = (1, 1, 1),
) -> List[BoundaryAtom]:
    """
    Generate periodic images of atoms that lie on cell boundaries (adaptive boundary repeat).
    
    Under Convention A: lattice is the supercell lattice; fractional coords are interpreted
    with respect to that lattice. For supercell mode with factors (m,n,l), the per-dimension
    tolerance is scaled: boundary_tol_x = boundary_tol / m, etc., so that the real-space
    thickness is approximately invariant vs supercell size.
    
    Boundary detection uses the representative coordinate system (frep) directly:
    - Detection boundaries are 0/1 in the representative system, NOT the canonical interval [lo, hi).
    - For an atom at fractional coordinate frep (already canonicalized to [-wrap_tol, 1-wrap_tol)):
      * If abs(frep[d] - 0.0) < tol_dim[d], it is near the 0-boundary and generates a +1 shift image
      * If abs(frep[d] - 1.0) < tol_dim[d], it is near the 1-boundary and generates a -1 shift image
    - Negative small frep values (e.g., -0.001) are treated as "near 0" by design, avoiding 0 being a knife-edge.
    - This is intentionally NOT mod1/physical [0,1) interpretation; it uses representative coords as truth.
    
    IMPORTANT: Base atoms are canonicalized for consistent boundary detection, but
    image atoms are NOT canonicalized. They are generated only via integer lattice translations
    (f_img = frep + shift_vec where shift_vec has components in {-1, 0, +1}).
    No wrapping, snapping, or geometry modification occurs on image atoms.
    
    Args:
        structure: pymatgen Structure object (already canonicalized, frep is in [-wrap_tol, 1-wrap_tol))
        boundary_tol: Tolerance for boundary detection in fractional coordinates (defaults to BOUNDARY_TOL = 0.01)
        wrap_tol: Wrap tolerance defining canonical interval [lo, lo+1) where lo = -wrap_tol (defaults to WRAP_TOL = 1e-4)
        supercell_factors: Tuple of (m, n, l) supercell scaling factors (defaults to (1,1,1) for primitive)
                          Used to scale boundary_tol per dimension: tol_dim = boundary_tol / factor
        
    Returns:
        List of BoundaryAtom objects (periodic images with fractional coords = frep + integer shift)
    """
    boundary_atoms: List[BoundaryAtom] = []
    lattice = structure.lattice
    
    # Compute per-dimension tolerances (scaled by supercell factors)
    tol_per_dim = np.array([
        boundary_tol / supercell_factors[0],
        boundary_tol / supercell_factors[1],
        boundary_tol / supercell_factors[2],
    ])
    
    for idx, site in enumerate(structure):
        # Use already-canonicalized fractional coordinates (frep in representative system)
        # Structure should have been canonicalized at the entry point via canonicalize_structure_in_place
        # We only inspect these coords to decide which atoms are on boundaries
        frac = np.array(site.frac_coords)  # This is frep
        symbol = site.specie.symbol
        
        # Generate all combinations of shifts for boundary atoms
        # Use abs(frep - 0) and abs(frep - 1) in representative system (NOT lo/hi)
        shifts_list = []
        for dim in range(3):
            f_dim = frac[dim]  # frep[dim]
            tol_dim_val = tol_per_dim[dim]
            
            # Check if near 0-boundary (two-sided band around 0 in representative system)
            near0 = abs(f_dim - 0.0) < tol_dim_val
            # Check if near 1-boundary (two-sided band around 1 in representative system)
            near1 = abs(f_dim - 1.0) < tol_dim_val
            
            # Determine allowed shifts for this dimension
            shifts_d = {0}  # Always include original position
            if near0:
                shifts_d.add(+1)  # Near 0, replicate at +1
            if near1:
                shifts_d.add(-1)  # Near 1, replicate at -1
            
            shifts_list.append(sorted(shifts_d))
        
        # Generate all shift combinations (except [0,0,0] which is original)
        from itertools import product
        for shift in product(*shifts_list):
            if shift == (0, 0, 0):
                continue  # Skip original position
            
            # CRITICAL: Do NOT canonicalize the shifted coordinates
            # Image atoms are generated only via integer lattice translations: f_img = frep + shift_vec
            # No wrapping, snapping, or geometry modification occurs
            new_frac = frac + np.array(shift, dtype=float)
            # Convert to Cartesian using the raw (non-canonicalized) fractional coordinates
            new_cart = lattice.get_cartesian_coords(new_frac)
            
            boundary_atoms.append(BoundaryAtom(
                original_idx=idx,
                coords=new_cart,
                frac_coords=new_frac,  # frep + integer shift
                symbol=symbol,
            ))
    
    return boundary_atoms


# =============================================================================
# Supercell expansion
# =============================================================================

def make_supercell(
    structure: PMGStructure,
    scaling: Union[int, Tuple[int, int, int]],
) -> PMGStructure:
    """
    Create a supercell of the structure.
    
    IMPORTANT: This function assumes the input structure has already been canonicalized
    at the primitive stage via canonicalize_structure_in_place(). It does NOT perform
    any canonicalization itself - it only applies integer lattice translations / supercell
    matrices to build the supercell.
    
    This function must NOT fold coordinates into [0,1). It preserves representative coords
    and only applies integer translations. We pass to_unit_cell=False explicitly to pymatgen
    to prevent any implicit coordinate folding that could violate our canonicalization contract.
    
    Args:
        structure: Original pymatgen Structure (should already be canonicalized)
        scaling: Tuple of (a, b, c) scaling factors, or int for (n, n, n)
        
    Returns:
        New Structure object representing the supercell (with non-canonicalized fractional coords
        that may be outside [0, 1) due to supercell expansion)
    """
    scaling = _normalize_supercell(scaling)
    if scaling == (1, 1, 1):
        return structure.copy()
    
    # Simply create the supercell - no canonicalization here
    # The input structure should already be canonicalized at the primitive stage
    supercell = structure.copy()
    # CRITICAL: do not fold/wrap again; canonicalization happens only once at entry.
    try:
        supercell.make_supercell(scaling, to_unit_cell=False)
    except TypeError:
        # Older pymatgen: no to_unit_cell kwarg; best-effort: call without it
        supercell.make_supercell(scaling)
    
    return supercell


# =============================================================================
# Conventional cell
# =============================================================================

def get_conventional_cell(
    structure: PMGStructure,
) -> PMGStructure:
    """
    Get the conventional/standard cell using pymatgen's SpacegroupAnalyzer.
    
    Args:
        structure: Original pymatgen Structure
        
    Returns:
        Conventional standard structure
        
    Raises:
        ValueError: If symmetry analysis fails
    """
    try:
        analyzer = SpacegroupAnalyzer(structure)
        conventional = analyzer.get_conventional_standard_structure()
        return conventional
    except Exception as e:
        logger.warning(f"Failed to get conventional cell: {e}. Using original structure.")
        return structure.copy()


# =============================================================================
# Box enumeration (Method 2: solve k-range intervals)
# =============================================================================

@dataclass
class DisplayAtom:
    """An atom in the display set with stable ID."""
    stable_id: str  # Stable identifier (e.g., "atom_0_trans_1_2_3")
    element: str
    cart_coords: np.ndarray
    frac_coords: np.ndarray
    original_idx: int  # Index in original structure
    translation: Tuple[int, int, int]  # Translation (i, j, k)


def enumerate_atoms_in_aabb(
    structure: PMGStructure,
    box_bounds: Tuple[float, float, float, float, float, float],
    *,
    eps: float = 1e-6,
) -> List[DisplayAtom]:
    """
    Enumerate all atoms inside an axis-aligned bounding box (AABB).
    
    Uses Method 2: solve k-range intervals to avoid generating huge supercells.
    
    For each basis atom r0 = A * f (where A is lattice matrix, f is fractional):
    - Find integer translations n=(i,j,k) such that:
      r = r0 + i*a + j*b + k*c lies inside [xmin,xmax]×[ymin,ymax]×[zmin,zmax]
    
    Algorithm:
    1) Compute tight bounds for i,j,k by mapping box corners through A^{-1}
    2) For each (i,j), derive k-interval constraints from x,y,z inequalities
    3) Intersect the three k-intervals and convert to integer k range
    4) For k in that range, compute r and accept if inside box (with eps)
    
    Args:
        structure: pymatgen Structure object
        box_bounds: (xmin, xmax, ymin, ymax, zmin, zmax) in Cartesian coordinates
        eps: Epsilon for boundary inclusion
        
    Returns:
        List of DisplayAtom objects with stable IDs
    """
    xmin, xmax, ymin, ymax, zmin, zmax = box_bounds
    
    # Validate bounds
    if xmax < xmin or ymax < ymin or zmax < zmin:
        return []
    
    lattice = structure.lattice
    A = lattice.matrix  # 3x3 matrix [a, b, c] as rows
    A_inv = np.linalg.inv(A)  # Inverse for fractional conversion
    
    display_atoms: List[DisplayAtom] = []
    
    # Get 8 box corners
    box_corners = np.array([
        [xmin, ymin, zmin],
        [xmax, ymin, zmin],
        [xmin, ymax, zmin],
        [xmin, ymin, zmax],
        [xmax, ymax, zmin],
        [xmax, ymin, zmax],
        [xmin, ymax, zmax],
        [xmax, ymax, zmax],
    ])
    
    # For each basis atom
    for orig_idx, site in enumerate(structure):
        r0 = np.array(site.coords)  # Original position
        f0 = np.array(site.frac_coords)  # Original fractional
        symbol = site.specie.symbol
        
        # Step 1: Compute tight bounds for i, j, k
        # Map box corners through A^{-1} relative to r0
        i_bounds = []
        j_bounds = []
        k_bounds = []
        
        for corner in box_corners:
            # Convert (corner - r0) to fractional coordinates
            delta = corner - r0
            n_frac = A_inv @ delta
            
            i_bounds.append(n_frac[0])
            j_bounds.append(n_frac[1])
            k_bounds.append(n_frac[2])
        
        i_min = int(np.floor(min(i_bounds))) - 1
        i_max = int(np.ceil(max(i_bounds))) + 1
        j_min = int(np.floor(min(j_bounds))) - 1
        j_max = int(np.ceil(max(j_bounds))) + 1
        
        # Step 2: For each (i, j), solve for k-interval
        for i in range(i_min, i_max + 1):
            for j in range(j_min, j_max + 1):
                # Compute r_ij = r0 + i*a + j*b
                r_ij = r0 + i * A[0] + j * A[1]
                
                # For each axis (x, y, z), derive k constraint
                # r = r_ij + k * c
                # For axis t: tmin <= r_ij[t] + k * c[t] <= tmax
                k_intervals = []
                
                for axis_idx, (tmin, tmax) in enumerate([(xmin, xmax), (ymin, ymax), (zmin, zmax)]):
                    c_t = A[2, axis_idx]  # c vector component along this axis
                    r_ij_t = r_ij[axis_idx]
                    
                    if abs(c_t) < eps:
                        # c_t ~ 0: constraint becomes feasibility check
                        if not (tmin - eps <= r_ij_t <= tmax + eps):
                            k_intervals = None  # Infeasible
                            break
                        # No constraint on k from this axis
                        continue
                    
                    # Solve: tmin <= r_ij_t + k * c_t <= tmax
                    # k >= (tmin - r_ij_t) / c_t  and  k <= (tmax - r_ij_t) / c_t
                    if c_t > 0:
                        k_lower = (tmin - r_ij_t) / c_t
                        k_upper = (tmax - r_ij_t) / c_t
                    else:
                        # c_t < 0: inequalities flip
                        k_lower = (tmax - r_ij_t) / c_t
                        k_upper = (tmin - r_ij_t) / c_t
                    
                    k_intervals.append((k_lower, k_upper))
                
                if k_intervals is None:
                    continue  # Infeasible for this (i, j)
                
                # Step 3: Intersect k-intervals
                if not k_intervals:
                    # All axes had c_t ~ 0, check if r_ij is in box
                    if (xmin - eps <= r_ij[0] <= xmax + eps and
                        ymin - eps <= r_ij[1] <= ymax + eps and
                        zmin - eps <= r_ij[2] <= zmax + eps):
                        k = 0
                        r = r_ij
                        stable_id = f"atom_{orig_idx}_trans_{i}_{j}_{k}"
                        f_new = f0 + np.array([i, j, k])
                        display_atoms.append(DisplayAtom(
                            stable_id=stable_id,
                            element=symbol,
                            cart_coords=r,
                            frac_coords=f_new,
                            original_idx=orig_idx,
                            translation=(i, j, k),
                        ))
                    continue
                
                # Intersect intervals
                k_lower = max(interval[0] for interval in k_intervals)
                k_upper = min(interval[1] for interval in k_intervals)
                
                if k_lower > k_upper + eps:
                    continue  # No solution
                
                # Step 4: Convert to integer k range
                k_min = int(np.floor(k_lower - eps))
                k_max = int(np.ceil(k_upper + eps))
                
                for k in range(k_min, k_max + 1):
                    r = r_ij + k * A[2]
                    
                    # Final check: is r inside box?
                    if (xmin - eps <= r[0] <= xmax + eps and
                        ymin - eps <= r[1] <= ymax + eps and
                        zmin - eps <= r[2] <= zmax + eps):
                        stable_id = f"atom_{orig_idx}_trans_{i}_{j}_{k}"
                        f_new = f0 + np.array([i, j, k])
                        display_atoms.append(DisplayAtom(
                            stable_id=stable_id,
                            element=symbol,
                            cart_coords=r,
                            frac_coords=f_new,
                            original_idx=orig_idx,
                            translation=(i, j, k),
                        ))
    
    return display_atoms


# =============================================================================
# Display atom building (unified for all modes)
# =============================================================================

@dataclass
class DisplayModeParams:
    """Parameters for different display modes."""
    mode: str  # "primitive", "supercell", "conventional", "box"
    supercell: Optional[Tuple[int, int, int]] = None
    box_bounds: Optional[Tuple[float, float, float, float, float, float]] = None
    repeat_boundary: bool = False


def build_display_atoms(
    structure: PMGStructure,
    params: DisplayModeParams,
    *,
    wrap_coords: bool = True,
) -> Tuple[List[DisplayAtom], PMGStructure]:
    """
    Build display atoms for any display mode.
    
    This is the unified function that all modes use to generate atoms.
    
    CRITICAL: Canonicalization happens exactly once at the very beginning on the
    primitive structure using pure shifted wrap (representative selection only).
    After that, all downstream operations (supercell, boundary images) operate on
    these already-canonicalized coordinates (frep) without further canonicalization.
    
    Boundary repeat uses adaptive algorithm with supercell-aware tolerance scaling:
    - For supercell mode with factors (m,n,l), per-dimension tolerance = boundary_tol / factor
    - This ensures real-space thickness is approximately invariant vs supercell size
    - Boundary detection uses abs(frep - 0) and abs(frep - 1) in the representative system
    - Negative small frep values (e.g., -0.001) are treated as "near 0" by design, avoiding 0 being a knife-edge
    - This is intentionally NOT mod1/physical [0,1) interpretation; it uses representative coords as truth
    - Images are generated only via integer lattice translations (f_img = frep + shift_vec)
    - No wrapping, snapping, or geometry modification occurs on image atoms
    
    Args:
        structure: Original pymatgen Structure
        params: DisplayModeParams specifying mode and parameters
        wrap_coords: Ignored (kept for backward compatibility). Canonicalization is done once at entry.
        
    Returns:
        Tuple of (list of DisplayAtom objects, display structure)
    """
    # CRITICAL: Canonicalize exactly once at the entry point on the primitive structure
    # This is the ONLY place we canonicalize fractional coordinates
    # Uses pure shifted wrap (no snapping) with wrap_tol
    structure_canon = structure.copy()
    canonicalize_structure_in_place(structure_canon, wrap_tol=WRAP_TOL)
    
    display_atoms: List[DisplayAtom] = []
    display_structure: PMGStructure
    
    # Determine supercell factors for boundary repeat scaling
    # For non-supercell modes, use (1,1,1)
    if params.mode == "supercell":
        supercell_factors = params.supercell if params.supercell is not None else (1, 1, 1)
    else:
        supercell_factors = (1, 1, 1)
    
    if params.mode == "primitive":
        # Primitive cell - use already-canonicalized structure
        display_structure = structure_canon.copy()
        
        # CRITICAL: Ensure cart_coords are computed from display_structure's lattice
        # site.coords should already be correct, but we verify consistency
        for idx, site in enumerate(display_structure):
            # Use site.coords (cartesian) which is computed from site.frac_coords using site's lattice
            # This ensures consistency with the display_structure's lattice
            cart_from_lattice = display_structure.lattice.get_cartesian_coords(site.frac_coords)
            # Verify site.coords matches (should be identical, but this catches mismatches)
            if not np.allclose(site.coords, cart_from_lattice, atol=BOUNDARY_FRAC_TOL):
                logger.warning(
                    f"Coordinate mismatch in primitive mode for atom {idx}: "
                    f"site.coords={site.coords} vs computed={cart_from_lattice}"
                )
            
            display_atoms.append(DisplayAtom(
                stable_id=f"atom_{idx}",
                element=site.specie.symbol,
                cart_coords=np.array(site.coords),  # Use site.coords (already correct for display_structure's lattice)
                frac_coords=np.array(site.frac_coords),
                original_idx=idx,
                translation=(0, 0, 0),
            ))
        
        if params.repeat_boundary:
            # CRITICAL: generate_boundary_atoms uses display_structure's lattice
            # This ensures boundary atoms are in the same coordinate system as display atoms
            # For primitive mode, supercell_factors = (1,1,1)
            boundary_atoms = generate_boundary_atoms(
                display_structure,
                boundary_tol=BOUNDARY_TOL,
                wrap_tol=WRAP_TOL,
                supercell_factors=supercell_factors,
            )
            for ba in boundary_atoms:
                # Verify boundary atom coords are consistent with display_structure's lattice
                cart_from_lattice = display_structure.lattice.get_cartesian_coords(ba.frac_coords)
                if not np.allclose(ba.coords, cart_from_lattice, atol=1e-6):
                    logger.warning(
                        f"Boundary atom coordinate mismatch for atom {ba.original_idx}: "
                        f"ba.coords={ba.coords} vs computed={cart_from_lattice}"
                    )
                
                display_atoms.append(DisplayAtom(
                    stable_id=f"boundary_{ba.original_idx}_{ba.frac_coords}",
                    element=ba.symbol,
                    cart_coords=ba.coords,  # Already computed from display_structure's lattice
                    frac_coords=ba.frac_coords,
                    original_idx=ba.original_idx,
                    translation=(0, 0, 0),  # Boundary atoms are already shifted
                ))
    
    elif params.mode == "supercell":
        # Supercell mode - use already-canonicalized structure
        if params.supercell is None:
            params.supercell = (1, 1, 1)
        display_structure = make_supercell(structure_canon, params.supercell)
        # No wrapping - supercell coords may be outside [0, 1) and that's OK
        
        # CRITICAL: After supercell expansion, the lattice has changed
        # Ensure cart_coords are computed from the supercell's lattice
        for idx, site in enumerate(display_structure):
            # Verify cart_coords are consistent with display_structure's lattice
            cart_from_lattice = display_structure.lattice.get_cartesian_coords(site.frac_coords)
            if not np.allclose(site.coords, cart_from_lattice, atol=1e-6):
                logger.warning(
                    f"Coordinate mismatch in supercell mode for atom {idx}: "
                    f"site.coords={site.coords} vs computed={cart_from_lattice}"
                )
            
            display_atoms.append(DisplayAtom(
                stable_id=f"atom_{idx}",
                element=site.specie.symbol,
                cart_coords=np.array(site.coords),  # Use site.coords (correct for supercell lattice)
                frac_coords=np.array(site.frac_coords),
                original_idx=idx % len(structure),  # Map back to original
                translation=(0, 0, 0),  # Supercell expansion handled by pymatgen
            ))
        
        if params.repeat_boundary:
            # CRITICAL: generate_boundary_atoms uses display_structure's lattice
            # For supercell mode, pass supercell factors for tolerance scaling
            boundary_atoms = generate_boundary_atoms(
                display_structure,
                boundary_tol=BOUNDARY_TOL,
                wrap_tol=WRAP_TOL,
                supercell_factors=supercell_factors,
            )
            for ba in boundary_atoms:
                # Verify boundary atom coords are consistent with display_structure's lattice
                cart_from_lattice = display_structure.lattice.get_cartesian_coords(ba.frac_coords)
                if not np.allclose(ba.coords, cart_from_lattice, atol=BOUNDARY_FRAC_TOL):
                    logger.warning(
                        f"Boundary atom coordinate mismatch in supercell mode for atom {ba.original_idx}: "
                        f"ba.coords={ba.coords} vs computed={cart_from_lattice}"
                    )
                
                display_atoms.append(DisplayAtom(
                    stable_id=f"boundary_{ba.original_idx}_{ba.frac_coords}",
                    element=ba.symbol,
                    cart_coords=ba.coords,  # Already computed from display_structure's lattice
                    frac_coords=ba.frac_coords,
                    original_idx=ba.original_idx,
                    translation=(0, 0, 0),
                ))
    
    elif params.mode == "conventional":
        # Conventional cell mode - start from canonicalized structure
        try:
            display_structure = get_conventional_cell(structure_canon)
        except Exception:
            logger.warning("Failed to get conventional cell, using original")
            display_structure = structure_canon.copy()
        # No wrapping - conventional cell coords are already canonicalized
        
        # CRITICAL: After conventional cell transformation, the lattice has changed
        # Ensure cart_coords are computed from the conventional cell's lattice
        for idx, site in enumerate(display_structure):
            # Verify cart_coords are consistent with display_structure's lattice
            cart_from_lattice = display_structure.lattice.get_cartesian_coords(site.frac_coords)
            if not np.allclose(site.coords, cart_from_lattice, atol=1e-6):
                logger.warning(
                    f"Coordinate mismatch in conventional mode for atom {idx}: "
                    f"site.coords={site.coords} vs computed={cart_from_lattice}"
                )
            
            display_atoms.append(DisplayAtom(
                stable_id=f"conv_atom_{idx}",
                element=site.specie.symbol,
                cart_coords=np.array(site.coords),  # Use site.coords (correct for conventional lattice)
                frac_coords=np.array(site.frac_coords),
                original_idx=idx,
                translation=(0, 0, 0),
            ))
        
        if params.repeat_boundary:
            # CRITICAL: generate_boundary_atoms uses display_structure's lattice
            # For conventional mode, supercell_factors = (1,1,1)
            boundary_atoms = generate_boundary_atoms(
                display_structure,
                boundary_tol=BOUNDARY_TOL,
                wrap_tol=WRAP_TOL,
                supercell_factors=supercell_factors,
            )
            for ba in boundary_atoms:
                # Verify boundary atom coords are consistent with display_structure's lattice
                cart_from_lattice = display_structure.lattice.get_cartesian_coords(ba.frac_coords)
                if not np.allclose(ba.coords, cart_from_lattice, atol=BOUNDARY_FRAC_TOL):
                    logger.warning(
                        f"Boundary atom coordinate mismatch in conventional mode for atom {ba.original_idx}: "
                        f"ba.coords={ba.coords} vs computed={cart_from_lattice}"
                    )
                
                display_atoms.append(DisplayAtom(
                    stable_id=f"conv_boundary_{ba.original_idx}_{ba.frac_coords}",
                    element=ba.symbol,
                    cart_coords=ba.coords,  # Already computed from display_structure's lattice
                    frac_coords=ba.frac_coords,
                    original_idx=ba.original_idx,
                    translation=(0, 0, 0),
                ))
    
    elif params.mode == "box":
        # Box mode (uses canonicalized structure for enumeration)
        # IMPORTANT: Box mode is non-periodic, so repeat_boundary is ignored
        if params.box_bounds is None:
            raise ValueError("box_bounds required for box mode")
        
        display_atoms_list = enumerate_atoms_in_aabb(structure_canon, params.box_bounds)
        display_atoms = display_atoms_list
        
        # Debug logging
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                f"Box mode: n_atoms={len(display_atoms)}, "
                f"box_bounds={params.box_bounds}, "
                f"repeat_boundary={params.repeat_boundary} (ignored)"
            )
        
        # Create a minimal structure for display (just for lattice info)
        display_structure = structure.copy()
        # Remove all sites, we'll use display_atoms instead
        display_structure.remove_sites(range(len(display_structure)))
        for da in display_atoms:
            display_structure.append(da.element, da.cart_coords)
    
    else:
        raise ValueError(f"Unknown display mode: {params.mode}")
    
    return display_atoms, display_structure


# =============================================================================
# Plotting
# =============================================================================

@dataclass
class StructurePlotOptions:
    """Options for structure visualization."""
    supercell: Tuple[int, int, int] = (1, 1, 1)
    repeat_boundary: bool = False
    atom_scale: float = 100.0  # Marker size scaling
    bond_width: float = 1.5
    bond_color: str = "#666666"
    show_cell: bool = True
    cell_color: str = "#000000"
    cell_width: float = 1.0
    cell_alpha: float = 0.5
    figsize: Tuple[float, float] = (10, 10)
    dpi: int = 150
    view_elevation: float = 20.0
    view_azimuth: float = 45.0


def plot_structure_3d(
    structure: PMGStructure,
    options: Optional[StructurePlotOptions] = None,
    ax: Optional[Axes3D] = None,
    structure_canon: Optional[PMGStructure] = None,
) -> Tuple[plt.Figure, Axes3D]:
    """
    Create a 3D ball-and-stick plot of a crystal structure.
    
    Args:
        structure: pymatgen Structure object (used if structure_canon is None)
        options: Plotting options (uses defaults if None)
        ax: Optional existing 3D axes to plot on
        structure_canon: Optional pre-canonicalized structure (avoids double canonicalization)
        
    Returns:
        Tuple of (Figure, Axes3D)
    """
    if options is None:
        options = StructurePlotOptions()
    
    # Use pre-canonicalized structure if provided, otherwise canonicalize here
    if structure_canon is None:
        structure_canon = structure.copy()
        canonicalize_structure_in_place(structure_canon, wrap_tol=WRAP_TOL)
    
    # Normalize supercell and create supercell if requested
    supercell_scaling = _normalize_supercell(options.supercell)
    plot_structure = make_supercell(structure_canon, supercell_scaling)
    
    # Create figure if needed
    if ax is None:
        fig = plt.figure(figsize=options.figsize, dpi=options.dpi)
        ax = fig.add_subplot(111, projection='3d')
    else:
        fig = ax.get_figure()
    
    # Collect all atoms to plot (this is the exact list that will be rendered)
    atoms_to_plot: List[Tuple[np.ndarray, str, int]] = []  # (coords, symbol, original_idx)
    
    for idx, site in enumerate(plot_structure):
        atoms_to_plot.append((np.array(site.coords), site.specie.symbol, idx))
    
    # Add boundary atoms if requested
    if options.repeat_boundary:
        boundary_atoms = generate_boundary_atoms(
            plot_structure,
            boundary_tol=BOUNDARY_TOL,
            wrap_tol=WRAP_TOL,
            supercell_factors=supercell_scaling,
        )
        for ba in boundary_atoms:
            atoms_to_plot.append((ba.coords, ba.symbol, ba.original_idx))
    
    # CRITICAL: Compute bonds from the exact same atom list that's being rendered
    # This ensures bond indices match exactly with rendered atoms
    atoms_cart = np.array([coords for coords, _, _ in atoms_to_plot])
    species = [symbol for _, symbol, _ in atoms_to_plot]
    
    # Use public API (auto-resolves radii_map)
    bonds = build_bonds(
        atoms_cart,
        species=species,
        max_factor=1.2,
        tolerance=0.3,
        max_cutoff=3.5,
    )
    
    # Plot atoms (balls)
    for coords, symbol, _ in atoms_to_plot:
        color = get_element_color(symbol)
        radius = get_element_radius(symbol)
        size = options.atom_scale * (radius ** 2)  # Scale by r^2 for visual area
        
        ax.scatter(
            coords[0], coords[1], coords[2],
            c=color,
            s=size,
            edgecolors='black',
            linewidths=0.5,
            alpha=0.9,
            depthshade=True,
        )
    
    # Plot bonds (sticks)
    for bond in bonds:
        ax.plot(
            [bond.coord1[0], bond.coord2[0]],
            [bond.coord1[1], bond.coord2[1]],
            [bond.coord1[2], bond.coord2[2]],
            color=options.bond_color,
            linewidth=options.bond_width,
            alpha=0.8,
        )
    
    # Plot unit cell
    if options.show_cell:
        _plot_cell_wireframe(ax, plot_structure.lattice, options)
    
    # Set labels and aspect
    ax.set_xlabel('x (Å)')
    ax.set_ylabel('y (Å)')
    ax.set_zlabel('z (Å)')
    
    # Set equal aspect ratio
    _set_equal_aspect_3d(ax, plot_structure)
    
    # Set view angle
    ax.view_init(elev=options.view_elevation, azim=options.view_azimuth)
    
    # Clean up the plot
    ax.set_box_aspect([1, 1, 1])
    
    return fig, ax


def _plot_cell_wireframe(
    ax: Axes3D,
    lattice,
    options: StructurePlotOptions,
) -> None:
    """Plot the unit cell as a wireframe."""
    # Get cell vectors
    a1, a2, a3 = lattice.matrix
    origin = np.array([0.0, 0.0, 0.0])
    
    # Define the 8 corners of the parallelepiped
    corners = [
        origin,
        a1,
        a2,
        a3,
        a1 + a2,
        a1 + a3,
        a2 + a3,
        a1 + a2 + a3,
    ]
    
    # Define the 12 edges of the parallelepiped
    edges = [
        (0, 1), (0, 2), (0, 3),  # From origin
        (1, 4), (1, 5),          # From a1
        (2, 4), (2, 6),          # From a2
        (3, 5), (3, 6),          # From a3
        (4, 7), (5, 7), (6, 7),  # To opposite corner
    ]
    
    for i, j in edges:
        c1, c2 = corners[i], corners[j]
        ax.plot(
            [c1[0], c2[0]],
            [c1[1], c2[1]],
            [c1[2], c2[2]],
            color=options.cell_color,
            linewidth=options.cell_width,
            alpha=options.cell_alpha,
            linestyle='--',
        )


def _set_equal_aspect_3d(ax: Axes3D, structure: PMGStructure) -> None:
    """Set equal aspect ratio for 3D plot."""
    # Get all atom coordinates
    coords = np.array([site.coords for site in structure])
    
    if len(coords) == 0:
        return
    
    # Also include cell corners for proper scaling
    lattice = structure.lattice
    a1, a2, a3 = lattice.matrix
    origin = np.array([0.0, 0.0, 0.0])
    cell_corners = np.array([
        origin, a1, a2, a3, a1+a2, a1+a3, a2+a3, a1+a2+a3
    ])
    
    all_coords = np.vstack([coords, cell_corners])
    
    # Find data ranges
    x_range = all_coords[:, 0].max() - all_coords[:, 0].min()
    y_range = all_coords[:, 1].max() - all_coords[:, 1].min()
    z_range = all_coords[:, 2].max() - all_coords[:, 2].min()
    
    max_range = max(x_range, y_range, z_range)
    
    # Set limits
    x_mid = (all_coords[:, 0].max() + all_coords[:, 0].min()) / 2
    y_mid = (all_coords[:, 1].max() + all_coords[:, 1].min()) / 2
    z_mid = (all_coords[:, 2].max() + all_coords[:, 2].min()) / 2
    
    ax.set_xlim(x_mid - max_range/2 * 1.1, x_mid + max_range/2 * 1.1)
    ax.set_ylim(y_mid - max_range/2 * 1.1, y_mid + max_range/2 * 1.1)
    ax.set_zlim(z_mid - max_range/2 * 1.1, z_mid + max_range/2 * 1.1)


# =============================================================================
# High-level API
# =============================================================================

@dataclass
class StructureVisualizationResult:
    """Result of structure visualization."""
    output_path: Optional[Path] = None
    n_atoms: int = 0
    n_bonds: int = 0
    supercell: Tuple[int, int, int] = (1, 1, 1)
    repeat_boundary: bool = False
    
    def to_dict(self) -> dict:
        return {
            "output_path": str(self.output_path) if self.output_path else None,
            "n_atoms": self.n_atoms,
            "n_bonds": self.n_bonds,
            "supercell": list(self.supercell),
            "repeat_boundary": self.repeat_boundary,
        }


def visualize_structure(
    structure: PMGStructure,
    output_path: Optional[Path] = None,
    supercell: Union[int, Tuple[int, int, int]] = (1, 1, 1),
    repeat_boundary: bool = False,
    show: bool = False,
    plot_format: str = "png",
    **kwargs,
) -> StructureVisualizationResult:
    """
    Visualize a crystal structure as a 3D ball-and-stick plot.
    
    This is the main entry point for structure visualization.
    
    Args:
        structure: pymatgen Structure object
        output_path: Path to save the plot (None to not save)
        supercell: Tuple of (a, b, c) supercell scaling factors
        repeat_boundary: If True, show periodic images at cell boundaries
        show: If True, attempt to display interactively (may not work headless)
        plot_format: Output format (png, svg, pdf)
        **kwargs: Additional options passed to StructurePlotOptions
        
    Returns:
        StructureVisualizationResult with metadata
    """
    # Normalize supercell input
    supercell_normalized = _normalize_supercell(supercell)
    
    options = StructurePlotOptions(
        supercell=supercell_normalized,
        repeat_boundary=repeat_boundary,
        **{k: v for k, v in kwargs.items() if hasattr(StructurePlotOptions, k)},
    )
    
    # CRITICAL: Canonicalize exactly once at the entry point (not in plot_structure_3d)
    structure_canon = structure.copy()
    canonicalize_structure_in_place(structure_canon, wrap_tol=WRAP_TOL)
    
    # Create the plot (pass pre-canonicalized structure to avoid double canonicalization)
    fig, ax = plot_structure_3d(structure, options, structure_canon=structure_canon)
    
    # Count atoms and bonds (must match what plot_structure_3d does)
    # Reuse the canonicalized structure to avoid double canonicalization
    plot_structure = make_supercell(structure_canon, supercell_normalized)
    n_atoms = len(plot_structure)
    
    # Collect all display atoms (matching plot_structure_3d logic)
    atoms_to_count: List[Tuple[np.ndarray, str]] = []
    for site in plot_structure:
        atoms_to_count.append((np.array(site.coords), site.specie.symbol))
    
    if repeat_boundary:
        boundary_atoms = generate_boundary_atoms(
            plot_structure,
            boundary_tol=BOUNDARY_TOL,
            wrap_tol=WRAP_TOL,
            supercell_factors=supercell_normalized,
        )
        for ba in boundary_atoms:
            atoms_to_count.append((ba.coords, ba.symbol))
        n_atoms += len(boundary_atoms)
    
    # Compute bonds from display atoms (same as plot_structure_3d)
    atoms_cart = np.array([coords for coords, _ in atoms_to_count])
    species = [symbol for _, symbol in atoms_to_count]
    
    # Use public API (auto-resolves radii_map)
    bonds = build_bonds(
        atoms_cart,
        species=species,
        max_factor=1.2,
        tolerance=0.3,
        max_cutoff=3.5,
    )
    
    result = StructureVisualizationResult(
        n_atoms=n_atoms,
        n_bonds=len(bonds),
        supercell=supercell_normalized,
        repeat_boundary=repeat_boundary,
    )
    
    # Save if output path provided
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, format=plot_format, dpi=options.dpi, bbox_inches='tight')
        result.output_path = output_path
    
    # Show if requested
    if show:
        try:
            import matplotlib
            if matplotlib.get_backend().lower() != 'agg':
                plt.show()
            else:
                import warnings
                warnings.warn(
                    "Cannot show interactive plot with Agg backend. "
                    "Set a different backend or save to file instead."
                )
        except Exception:
            pass
    
    # Close figure to free memory
    plt.close(fig)

    return result


# =============================================================================
# Visualization Payload Builder (Pure Transformation)
# =============================================================================

def build_structure_vis_payload(
    structure: PMGStructure,
    params: DisplayModeParams,
    structure_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build visualization payload from a structure.

    Pure transformation: Structure + DisplayModeParams → visualization primitives dict.

    This is a kernel function that transforms a pymatgen Structure into a dict
    containing all data needed for 3D visualization (atoms, bonds, lattice).

    Args:
        structure: pymatgen Structure object
        params: DisplayModeParams with mode, supercell, box_bounds, repeat_boundary
        structure_meta: Optional metadata dict (structure_id, structure_name, formula)
            Used only for populating result fields, not for any computation.

    Returns:
        Dict with:
            - atoms: List of atom dicts with cart_coords, frac_coords, element, color, radius
            - bonds: List of bond dicts with idx1, idx2, coord1, coord2, distance
            - lattice: Dict with matrix, a, b, c, alpha, beta, gamma, volume
            - n_atoms, n_bonds: Counts
            - element_colors: Color mapping dict
            - Optional: structure_id, structure_name, formula, supercell, display_mode

    Note:
        - This is a pure transformation with no side effects (except logging)
        - Caller is responsible for JSON serialization if needed
        - Caller is responsible for timing/performance metrics if needed
    """
    # Build display atoms using the unified function
    display_atoms_list, display_structure = build_display_atoms(
        structure,
        params,
        wrap_coords=True,
    )

    # Get lattice info from display structure
    lattice = display_structure.lattice

    # Build atoms list
    # CONTRACT: atoms contains ALL display atoms (for rendering + bonds)
    # boundary atoms are marked with is_boundary flag
    atoms: List[Dict[str, Any]] = []
    for da in display_atoms_list:
        atom_dict = {
            "index": len(atoms),
            "original_idx": da.original_idx,
            "element": da.element,
            "cart_coords": [float(c) for c in da.cart_coords],
            "frac_coords": [float(f) for f in da.frac_coords],
            "color": get_element_color(da.element),
            "radius": get_element_radius(da.element),
        }
        # Mark boundary atoms for UI
        if "boundary" in da.stable_id:
            atom_dict["is_boundary"] = True
        atoms.append(atom_dict)

    # Build bonds using cartesian distances only
    # The display_atoms_list already includes all repeated/boundary atoms
    bonds: List[Dict[str, Any]] = []
    try:
        atoms_cart = np.array([da.cart_coords for da in display_atoms_list])
        species = [da.element for da in display_atoms_list]

        detected_bonds = build_bonds(
            atoms_cart,
            species=species,
            max_factor=1.2,
            tolerance=0.3,
            max_cutoff=3.5,
        )

        # Convert to dict format
        # CRITICAL: bonds.idx1/idx2 must reference atoms array (0 to len(atoms)-1)
        max_bond_idx = -1
        for bond in detected_bonds:
            idx1 = int(bond.idx1)
            idx2 = int(bond.idx2)
            max_bond_idx = max(max_bond_idx, idx1, idx2)
            bonds.append({
                "idx1": idx1,
                "idx2": idx2,
                "coord1": [float(c) for c in bond.coord1],
                "coord2": [float(c) for c in bond.coord2],
                "distance": float(bond.distance),
            })

        # Validate: bonds must only reference atoms array
        atoms_len = len(atoms)
        if bonds and max_bond_idx >= atoms_len:
            raise ValueError(
                f"Invalid bond indices: max={max_bond_idx} >= atoms_len={atoms_len}"
            )
    except Exception as e:
        logger.warning(f"Failed to build bonds: {e}")

    # Build result dict
    result: Dict[str, Any] = {
        "n_atoms": len(atoms),
        "n_bonds": len(bonds),
        "lattice": {
            "matrix": lattice.matrix.tolist(),
            "a": float(lattice.a),
            "b": float(lattice.b),
            "c": float(lattice.c),
            "alpha": float(lattice.alpha),
            "beta": float(lattice.beta),
            "gamma": float(lattice.gamma),
            "volume": float(lattice.volume),
        },
        "atoms": atoms,
        "boundary_atoms": [],  # DEPRECATED: Use atoms.filter(a=>a.is_boundary)
        "bonds": bonds,
        "element_colors": ELEMENT_COLORS,
    }

    # Add metadata if provided
    if structure_meta:
        result.update(structure_meta)

    # Ensure required fields exist
    if "structure_id" not in result:
        result["structure_id"] = structure_meta.get("structure_id", "unknown") if structure_meta else "unknown"
    if "structure_name" not in result:
        result["structure_name"] = structure_meta.get("structure_name", "") if structure_meta else ""
    if "formula" not in result:
        # Compute from atoms
        from collections import Counter
        element_counts = Counter(atom["element"] for atom in atoms)
        formula_parts = []
        for element, count in sorted(element_counts.items()):
            if count == 1:
                formula_parts.append(element)
            else:
                formula_parts.append(f"{element}{count}")
        result["formula"] = "".join(formula_parts)
    if "supercell" not in result:
        result["supercell"] = list(params.supercell) if params.supercell else [1, 1, 1]
    if "display_mode" not in result:
        result["display_mode"] = params.mode

    return result
