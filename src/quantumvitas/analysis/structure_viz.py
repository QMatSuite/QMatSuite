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

import matplotlib
matplotlib.use("Agg")  # Headless-safe backend

import numpy as np
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set, Union
from itertools import product
import logging

import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from pymatgen.core import Structure as PMGStructure
from pymatgen.core.periodic_table import Element
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer

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


# Covalent radii in Angstroms (from Cordero et al., Dalton Trans. 2008)
# Used for bond detection
COVALENT_RADII: Dict[str, float] = {
    "H": 0.31, "He": 0.28,
    "Li": 1.28, "Be": 0.96, "B": 0.84, "C": 0.76, "N": 0.71, "O": 0.66, "F": 0.57, "Ne": 0.58,
    "Na": 1.66, "Mg": 1.41, "Al": 1.21, "Si": 1.11, "P": 1.07, "S": 1.05, "Cl": 1.02, "Ar": 1.06,
    "K": 2.03, "Ca": 1.76, "Sc": 1.70, "Ti": 1.60, "V": 1.53, "Cr": 1.39, "Mn": 1.39, "Fe": 1.32,
    "Co": 1.26, "Ni": 1.24, "Cu": 1.32, "Zn": 1.22, "Ga": 1.22, "Ge": 1.20, "As": 1.19, "Se": 1.20,
    "Br": 1.20, "Kr": 1.16,
    "Rb": 2.20, "Sr": 1.95, "Y": 1.90, "Zr": 1.75, "Nb": 1.64, "Mo": 1.54, "Tc": 1.47, "Ru": 1.46,
    "Rh": 1.42, "Pd": 1.39, "Ag": 1.45, "Cd": 1.44, "In": 1.42, "Sn": 1.39, "Sb": 1.39, "Te": 1.38,
    "I": 1.39, "Xe": 1.40,
    "Cs": 2.44, "Ba": 2.15, "La": 2.07, "Ce": 2.04, "Pr": 2.03, "Nd": 2.01, "Pm": 1.99, "Sm": 1.98,
    "Eu": 1.98, "Gd": 1.96, "Tb": 1.94, "Dy": 1.92, "Ho": 1.92, "Er": 1.89, "Tm": 1.90, "Yb": 1.87,
    "Lu": 1.87, "Hf": 1.75, "Ta": 1.70, "W": 1.62, "Re": 1.51, "Os": 1.44, "Ir": 1.41, "Pt": 1.36,
    "Au": 1.36, "Hg": 1.32, "Tl": 1.45, "Pb": 1.46, "Bi": 1.48, "Po": 1.40, "At": 1.50, "Rn": 1.50,
    "Fr": 2.60, "Ra": 2.21, "Ac": 2.15, "Th": 2.06, "Pa": 2.00, "U": 1.96, "Np": 1.90, "Pu": 1.87,
}


def get_element_radius(symbol: str) -> float:
    """
    Get covalent radius for an element in Angstroms.
    
    Uses built-in covalent radii table, with fallback to pymatgen's atomic_radius.
    """
    # First check our built-in covalent radii table
    if symbol in COVALENT_RADII:
        return COVALENT_RADII[symbol]
    
    # Fallback to pymatgen's atomic_radius
    try:
        el = Element(symbol)
        if hasattr(el, 'atomic_radius') and el.atomic_radius is not None:
            return float(el.atomic_radius)
    except (ValueError, KeyError, AttributeError):
        pass
    
    return 1.0  # Default radius


# =============================================================================
# Wrapping and coordinate utilities
# =============================================================================

# Epsilon for boundary handling in fractional coordinates
FRAC_EPS = 1e-9


def wrap_fractional_coords(frac: np.ndarray, eps: float = FRAC_EPS) -> np.ndarray:
    """
    Wrap fractional coordinates into [0, 1) with epsilon handling.
    
    For a fractional coordinate f:
    - f_wrapped = f - floor(f)
    - If component is ~1.0 ( > 1 - eps ), set to 0.0
    
    Args:
        frac: Fractional coordinates (can be 1D or 2D array)
        eps: Epsilon for boundary detection
        
    Returns:
        Wrapped fractional coordinates in [0, 1)
    """
    frac = np.asarray(frac)
    was_1d = frac.ndim == 1
    if was_1d:
        frac = frac.reshape(1, -1)
    
    # Wrap: f - floor(f)
    wrapped = frac - np.floor(frac)
    
    # Handle components near 1.0: set to 0.0
    wrapped[wrapped > 1.0 - eps] = 0.0
    
    if was_1d:
        wrapped = wrapped.reshape(-1)
    
    return wrapped


def wrap_cartesian_coords(
    coords: np.ndarray,
    lattice,
    eps: float = FRAC_EPS,
) -> np.ndarray:
    """
    Wrap Cartesian coordinates into the unit cell.
    
    Converts to fractional, wraps, then back to Cartesian.
    
    Args:
        coords: Cartesian coordinates (can be 1D or 2D array)
        lattice: pymatgen Lattice object
        eps: Epsilon for boundary detection
        
    Returns:
        Wrapped Cartesian coordinates
    """
    coords = np.asarray(coords)
    was_1d = coords.ndim == 1
    if was_1d:
        coords = coords.reshape(1, -1)
    
    # Convert to fractional
    frac = np.array([lattice.get_fractional_coords(c) for c in coords])
    
    # Wrap
    frac_wrapped = wrap_fractional_coords(frac, eps)
    
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

@dataclass
class Bond:
    """Represents a bond between two atoms."""
    idx1: int  # Index of first atom
    idx2: int  # Index of second atom
    coord1: np.ndarray  # Coordinates of first atom
    coord2: np.ndarray  # Coordinates of second atom
    distance: float


def build_bonds(
    atoms_cart: np.ndarray,
    species: List[str],
    radii_map: Dict[str, float],
    *,
    max_factor: float = 1.2,
    tolerance: float = 0.3,
    max_cutoff: float = 3.5,
    neighbor_shell: Optional[int] = None,
    lattice_matrix: Optional[np.ndarray] = None,
) -> List[Bond]:
    """
    SINGLE SOURCE OF TRUTH for bond construction.
    
    Builds bonds for any atom set in Cartesian coordinates using radii-based
    distance threshold. Works for primitive, supercell, conventional, or box modes.
    
    Bond criterion: distance < (r_i + r_j) * max_factor + tolerance
    
    When lattice_matrix is provided, uses PBC-aware minimum-image convention
    to find bonds across periodic boundaries. This is essential for supercells
    where atoms at edges need to bond to neighbors in adjacent images.
    
    **PBC-aware bond detection**: When `lattice_matrix` is provided, bond distances
    are computed using minimum-image convention (fractional wrapping to [-0.5, 0.5)).
    This ensures correct connectivity in periodic structures. Invalid or near-singular
    lattice matrices fall back to non-periodic detection with a warning.
    
    **Performance**: For non-periodic mode, uses KD-tree (O(N log N)). For PBC mode,
    uses brute force with minimum-image (O(N²)) which is correct and fast enough
    for typical structure sizes (N < 1000). Both modes use a precomputed global
    cutoff to reduce candidate pairs.
    
    Args:
        atoms_cart: Array of shape (N, 3) with Cartesian coordinates
        species: List of N element symbols
        radii_map: Dictionary mapping element symbols to radii
        max_factor: Multiplier for sum of radii (default 1.2)
        tolerance: Extra tolerance in Å (default 0.3)
        max_cutoff: Maximum distance to consider in Å (default 3.5)
        neighbor_shell: Optional number of neighbor shells to consider
            (if None, uses distance-based cutoff)
        lattice_matrix: Optional 3x3 lattice matrix for PBC-aware distance calculation.
            Must be invertible and well-conditioned. If None or invalid, uses Euclidean
            distance (non-periodic). Invalid matrices trigger a warning and fallback.
        
    Returns:
        List of Bond objects with idx1 < idx2 (no duplicates)
        
    Note:
        **Semantics**: This function handles bond detection. Boundary atom display
        (boundary repeat) is separate and does not affect bond detection results.
    """
    atoms_cart = np.asarray(atoms_cart)
    n_atoms = len(atoms_cart)
    
    if n_atoms == 0:
        return []
    
    bonds: List[Bond] = []
    seen_bonds: Set[Tuple[int, int]] = set()
    
    # Compute inverse lattice matrix if PBC is enabled
    # Validate and handle invalid/near-singular matrices gracefully
    A = None
    A_inv = None
    if lattice_matrix is not None:
        A = np.asarray(lattice_matrix)
        if A.shape != (3, 3):
            logger.warning(
                f"lattice_matrix must be 3x3, got shape {A.shape}. "
                f"Falling back to non-periodic bond detection."
            )
            A = None
        else:
            try:
                # Check condition number to detect near-singular matrices
                cond = np.linalg.cond(A)
                if cond > 1e12:  # Very ill-conditioned
                    logger.warning(
                        f"lattice_matrix is near-singular (condition number {cond:.2e}). "
                        f"Falling back to non-periodic bond detection."
                    )
                    A = None
                else:
                    A_inv = np.linalg.inv(A)
            except np.linalg.LinAlgError:
                logger.warning(
                    "lattice_matrix is singular and cannot be inverted. "
                    "Falling back to non-periodic bond detection."
                )
                A = None
    
    # Precompute global maximum cutoff for candidate filtering
    # This helps reduce the number of pairs we need to check
    max_radius = max(radii_map.values()) if radii_map else 1.0
    global_max_cutoff = 2 * max_radius * max_factor + tolerance
    global_max_cutoff = min(global_max_cutoff, max_cutoff)  # Cap at user-specified max
    
    # Build KD-tree for efficient neighbor search
    # For PBC mode, we can still use KD-tree in Cartesian space for initial filtering,
    # then apply minimum-image distance only to candidates
    use_tree = True
    tree = None
    try:
        from scipy.spatial import cKDTree
        tree = cKDTree(atoms_cart)
    except ImportError:
        # Fallback to brute force if scipy not available
        logger.warning("scipy not available, using brute-force bond detection")
        use_tree = False
    
    for i in range(n_atoms):
        coord_i = atoms_cart[i]
        elem_i = species[i]
        radius_i = radii_map.get(elem_i, 1.0)
        
        # Find neighbor candidates
        neighbors = []
        if use_tree and tree is not None:
            # Use KD-tree for initial candidate search
            # Query with global_max_cutoff to get all potential neighbors
            # This reduces O(N²) to O(N log N) for candidate finding
            if A_inv is None:
                # Non-periodic: use KD-tree directly
                distances, indices = tree.query(
                    coord_i, 
                    k=min(n_atoms, 50), 
                    distance_upper_bound=global_max_cutoff
                )
                # Filter out self and invalid results
                neighbors = [(idx, dist) for idx, dist in zip(indices, distances) 
                            if idx < n_atoms and dist <= global_max_cutoff and idx != i]
            else:
                # PBC mode: For small structures, brute force is fast enough.
                # For larger structures, we could use KD-tree with a conservative radius,
                # but for correctness and simplicity, use brute force with minimum-image.
                # The KD-tree optimization can miss neighbors that are close via PBC
                # but far in Cartesian space.
                for j in range(n_atoms):
                    if j == i:
                        continue
                    # Compute minimum-image distance
                    frac_i = A_inv @ coord_i
                    frac_j = A_inv @ atoms_cart[j]
                    delta_frac = frac_j - frac_i
                    delta_frac = delta_frac - np.round(delta_frac)
                    # Epsilon guard for numerical stability
                    EPS_WRAP = 1e-10
                    delta_frac = np.where(
                        np.abs(np.abs(delta_frac) - 0.5) < EPS_WRAP,
                        np.sign(delta_frac) * 0.5,
                        delta_frac
                    )
                    delta_cart = A @ delta_frac
                    dist = np.linalg.norm(delta_cart)
                    if dist <= global_max_cutoff:
                        neighbors.append((j, dist))
        else:
            # Brute force fallback
            for j in range(n_atoms):
                if i == j:
                    continue
                
                if A_inv is not None:
                    # PBC-aware: use minimum-image convention
                    frac_i = A_inv @ coord_i
                    frac_j = A_inv @ atoms_cart[j]
                    delta_frac = frac_j - frac_i
                    delta_frac = delta_frac - np.round(delta_frac)
                    # Epsilon guard for numerical stability
                    EPS_WRAP = 1e-10
                    delta_frac = np.where(
                        np.abs(np.abs(delta_frac) - 0.5) < EPS_WRAP,
                        np.sign(delta_frac) * 0.5,
                        delta_frac
                    )
                    delta_cart = A @ delta_frac
                    dist = np.linalg.norm(delta_cart)
                else:
                    # Non-periodic: Euclidean distance
                    dist = np.linalg.norm(atoms_cart[j] - coord_i)
                
                if dist <= global_max_cutoff:
                    neighbors.append((j, dist))
        
        for j, dist in neighbors:
            if i >= j:  # Only consider i < j to avoid duplicates
                continue
            
            elem_j = species[j]
            radius_j = radii_map.get(elem_j, 1.0)
            
            # Bond criterion
            max_bond_dist = (radius_i + radius_j) * max_factor + tolerance
            
            if dist <= max_bond_dist:
                # Check if we've seen this bond
                bond_key = (i, j)
                if bond_key not in seen_bonds:
                    seen_bonds.add(bond_key)
                    # For PBC bonds, use the minimum-image coordinates
                    if A_inv is not None:
                        frac_i = A_inv @ coord_i
                        frac_j = A_inv @ atoms_cart[j]
                        delta_frac = frac_j - frac_i
                        delta_frac = delta_frac - np.round(delta_frac)
                        # Apply same epsilon guard for coordinate computation
                        EPS_WRAP = 1e-10
                        delta_frac = np.where(
                            np.abs(np.abs(delta_frac) - 0.5) < EPS_WRAP,
                            np.sign(delta_frac) * 0.5,
                            delta_frac
                        )
                        coord_j_min_image = coord_i + (A @ delta_frac)
                    else:
                        coord_j_min_image = atoms_cart[j].copy()
                    
                    bonds.append(Bond(
                        idx1=i,
                        idx2=j,
                        coord1=coord_i.copy(),
                        coord2=coord_j_min_image,
                        distance=float(dist),
                    ))
    
    return bonds


# Legacy function for backward compatibility
def detect_bonds(
    structure: PMGStructure,
    tolerance: float = 0.3,
    max_cutoff: float = 3.5,
    include_periodic_images: bool = True,  # DEPRECATED: No longer affects bond detection
) -> List[Bond]:
    """
    Detect bonds in a structure based on covalent radii (legacy function).
    
    This function is kept for backward compatibility but now uses build_bonds
    internally. For new code, use build_bonds directly.
    
    .. deprecated:: 
        The `include_periodic_images` parameter is deprecated and no longer affects
        bond detection results. Bond detection always uses PBC-aware minimum-image
        convention for periodic structures. The parameter is kept for backward
        compatibility only.
    
    Args:
        structure: pymatgen Structure object
        tolerance: Extra tolerance for bond detection (Å)
        max_cutoff: Maximum distance to consider (Å)
        include_periodic_images: DEPRECATED - No longer affects bond detection.
            Bond detection always uses PBC-aware minimum-image convention.
            This parameter is kept for backward compatibility only.
        
    Returns:
        List of Bond objects
        
    Note:
        **Semantics clarification:**
        - **PBC bond detection**: Always used for periodic structures via minimum-image
          convention. This ensures correct connectivity (e.g., 32 bonds in Si 2×2×2 supercell).
        - **Boundary repeat** (display): Controls whether boundary atoms/images are displayed
          for visualization. This is separate from bond detection and does not affect
          bond counts or connectivity.
    """
    # Extract atoms and species
    atoms_cart = np.array([site.coords for site in structure])
    species = [site.specie.symbol for site in structure]
    
    # Build radii map
    radii_map = {sym: get_element_radius(sym) for sym in set(species)}
    
    # Get lattice matrix for PBC-aware bond detection
    # PBC is ALWAYS used for bond detection (minimum-image convention)
    # The include_periodic_images parameter is deprecated and ignored
    lattice_matrix = structure.lattice.matrix
    
    # Use single-source-of-truth function with PBC-aware distance
    return build_bonds(
        atoms_cart,
        species,
        radii_map,
        tolerance=tolerance,
        max_cutoff=max_cutoff,
        lattice_matrix=lattice_matrix,  # Always use PBC for correct bond detection
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
    tolerance: float = 1e-6,
) -> List[BoundaryAtom]:
    """
    Generate periodic images of atoms that lie on cell boundaries.
    
    For an atom at fractional coordinate f:
    - If f < tolerance, it lies on the "lower" boundary and should be replicated at f+1
    - This creates the visual effect of atoms shared between adjacent cells
    
    Args:
        structure: pymatgen Structure object
        tolerance: Tolerance for boundary detection in fractional coordinates
        
    Returns:
        List of BoundaryAtom objects (periodic images)
    """
    boundary_atoms: List[BoundaryAtom] = []
    lattice = structure.lattice
    
    for idx, site in enumerate(structure):
        frac = np.array(site.frac_coords)
        symbol = site.specie.symbol
        
        # Check each dimension for boundary proximity
        on_boundary = [
            abs(frac[dim]) < tolerance or abs(frac[dim] - 1.0) < tolerance
            for dim in range(3)
        ]
        
        # Generate all combinations of shifts for boundary atoms
        shifts_list = []
        for dim in range(3):
            if abs(frac[dim]) < tolerance:
                # Near 0, replicate at +1
                shifts_list.append([0, 1])
            elif abs(frac[dim] - 1.0) < tolerance:
                # Near 1, replicate at 0 (i.e., shift by -1)
                shifts_list.append([0, -1])
            else:
                shifts_list.append([0])
        
        # Generate all shift combinations (except [0,0,0] which is original)
        from itertools import product
        for shift in product(*shifts_list):
            if shift == (0, 0, 0):
                continue  # Skip original position
            
            new_frac = frac + np.array(shift)
            # Keep within [0, 1] range for display
            new_frac = np.mod(new_frac + tolerance, 1.0 + 2*tolerance) - tolerance
            new_cart = lattice.get_cartesian_coords(new_frac)
            
            boundary_atoms.append(BoundaryAtom(
                original_idx=idx,
                coords=new_cart,
                frac_coords=new_frac,
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
    
    Args:
        structure: Original pymatgen Structure
        scaling: Tuple of (a, b, c) scaling factors, or int for (n, n, n)
        
    Returns:
        New Structure object representing the supercell
    """
    scaling = _normalize_supercell(scaling)
    if scaling == (1, 1, 1):
        return structure.copy()
    
    supercell = structure.copy()
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
    
    Args:
        structure: Original pymatgen Structure
        params: DisplayModeParams specifying mode and parameters
        wrap_coords: If True, wrap all coordinates into display cell
        
    Returns:
        Tuple of (list of DisplayAtom objects, display structure)
    """
    display_atoms: List[DisplayAtom] = []
    display_structure: PMGStructure
    
    if params.mode == "primitive":
        # Primitive cell (wrapped)
        display_structure = structure.copy()
        if wrap_coords:
            # Wrap all atoms into [0,1) fractional
            for site in display_structure:
                frac = wrap_fractional_coords(site.frac_coords)
                site.frac_coords = frac
        
        for idx, site in enumerate(display_structure):
            display_atoms.append(DisplayAtom(
                stable_id=f"atom_{idx}",
                element=site.specie.symbol,
                cart_coords=np.array(site.coords),
                frac_coords=np.array(site.frac_coords),
                original_idx=idx,
                translation=(0, 0, 0),
            ))
        
        if params.repeat_boundary:
            boundary_atoms = generate_boundary_atoms(display_structure)
            for ba in boundary_atoms:
                display_atoms.append(DisplayAtom(
                    stable_id=f"boundary_{ba.original_idx}_{ba.frac_coords}",
                    element=ba.symbol,
                    cart_coords=ba.coords,
                    frac_coords=ba.frac_coords,
                    original_idx=ba.original_idx,
                    translation=(0, 0, 0),  # Boundary atoms are already shifted
                ))
    
    elif params.mode == "supercell":
        # Supercell mode
        if params.supercell is None:
            params.supercell = (1, 1, 1)
        display_structure = make_supercell(structure, params.supercell)
        
        if wrap_coords:
            # Wrap all atoms
            for site in display_structure:
                frac = wrap_fractional_coords(site.frac_coords)
                site.frac_coords = frac
        
        for idx, site in enumerate(display_structure):
            display_atoms.append(DisplayAtom(
                stable_id=f"atom_{idx}",
                element=site.specie.symbol,
                cart_coords=np.array(site.coords),
                frac_coords=np.array(site.frac_coords),
                original_idx=idx % len(structure),  # Map back to original
                translation=(0, 0, 0),  # Supercell expansion handled by pymatgen
            ))
        
        if params.repeat_boundary:
            boundary_atoms = generate_boundary_atoms(display_structure)
            for ba in boundary_atoms:
                display_atoms.append(DisplayAtom(
                    stable_id=f"boundary_{ba.original_idx}_{ba.frac_coords}",
                    element=ba.symbol,
                    cart_coords=ba.coords,
                    frac_coords=ba.frac_coords,
                    original_idx=ba.original_idx,
                    translation=(0, 0, 0),
                ))
    
    elif params.mode == "conventional":
        # Conventional cell mode
        try:
            display_structure = get_conventional_cell(structure)
        except Exception:
            logger.warning("Failed to get conventional cell, using original")
            display_structure = structure.copy()
        
        if wrap_coords:
            for site in display_structure:
                frac = wrap_fractional_coords(site.frac_coords)
                site.frac_coords = frac
        
        for idx, site in enumerate(display_structure):
            display_atoms.append(DisplayAtom(
                stable_id=f"conv_atom_{idx}",
                element=site.specie.symbol,
                cart_coords=np.array(site.coords),
                frac_coords=np.array(site.frac_coords),
                original_idx=idx,
                translation=(0, 0, 0),
            ))
        
        if params.repeat_boundary:
            boundary_atoms = generate_boundary_atoms(display_structure)
            for ba in boundary_atoms:
                display_atoms.append(DisplayAtom(
                    stable_id=f"conv_boundary_{ba.original_idx}_{ba.frac_coords}",
                    element=ba.symbol,
                    cart_coords=ba.coords,
                    frac_coords=ba.frac_coords,
                    original_idx=ba.original_idx,
                    translation=(0, 0, 0),
                ))
    
    elif params.mode == "box":
        # Box mode (uses original structure for enumeration)
        # IMPORTANT: Box mode is non-periodic, so repeat_boundary is ignored
        if params.box_bounds is None:
            raise ValueError("box_bounds required for box mode")
        
        display_atoms_list = enumerate_atoms_in_aabb(structure, params.box_bounds)
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
) -> Tuple[plt.Figure, Axes3D]:
    """
    Create a 3D ball-and-stick plot of a crystal structure.
    
    Args:
        structure: pymatgen Structure object
        options: Plotting options (uses defaults if None)
        ax: Optional existing 3D axes to plot on
        
    Returns:
        Tuple of (Figure, Axes3D)
    """
    if options is None:
        options = StructurePlotOptions()
    
    # Normalize supercell and create supercell if requested
    supercell_scaling = _normalize_supercell(options.supercell)
    plot_structure = make_supercell(structure, supercell_scaling)
    
    # Create figure if needed
    if ax is None:
        fig = plt.figure(figsize=options.figsize, dpi=options.dpi)
        ax = fig.add_subplot(111, projection='3d')
    else:
        fig = ax.get_figure()
    
    # Collect all atoms to plot
    atoms_to_plot: List[Tuple[np.ndarray, str, int]] = []  # (coords, symbol, original_idx)
    
    for idx, site in enumerate(plot_structure):
        atoms_to_plot.append((np.array(site.coords), site.specie.symbol, idx))
    
    # Add boundary atoms if requested
    if options.repeat_boundary:
        boundary_atoms = generate_boundary_atoms(plot_structure)
        for ba in boundary_atoms:
            atoms_to_plot.append((ba.coords, ba.symbol, ba.original_idx))
    
    # Detect bonds using PBC-aware minimum-image convention
    # Note: repeat_boundary only affects boundary atom display, not bond detection.
    # Bond detection always uses PBC-aware minimum-image convention for periodic structures.
    bonds = detect_bonds(plot_structure, include_periodic_images=options.repeat_boundary)
    
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
    
    # Create the plot
    fig, ax = plot_structure_3d(structure, options)
    
    # Create supercell for counting (must match what plot_structure_3d does)
    plot_structure = make_supercell(structure, supercell_normalized)
    bonds = detect_bonds(plot_structure, include_periodic_images=repeat_boundary)
    
    # Count atoms (including boundary if applicable)
    n_atoms = len(plot_structure)
    if repeat_boundary:
        boundary_atoms = generate_boundary_atoms(plot_structure)
        n_atoms += len(boundary_atoms)
    
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
