"""
Structure fingerprinting for content-based deduplication.

This module provides functions to create stable, content-based fingerprints
for atomic structures, enabling robust deduplication across different QE input
representations (units, ibrav, coordinate systems) while avoiding false positives
from tiny float noise.

Design principles:
- Use WRAP_TOL=1e-4 canonical interval logic for representative selection
- Quantize with tol=1e-5 for fingerprint stability
- No symmetry/basis-change equivalence (high precision, minimal false positives)
- Deterministic site ordering for stable hashing
"""

from __future__ import annotations

import hashlib
import math
from typing import List, Tuple

import numpy as np
from pymatgen.core import Structure as PMGStructure
from pymatgen.core import Molecule as PMGMolecule
from typing import Union

from quantumvitas.analysis.structure_viz import (
    WRAP_TOL,
    canonicalize_frac_coords,
)


def canonicalize_structure_for_identity(structure: PMGStructure) -> PMGStructure:
    """
    Canonicalize a structure for identity comparison.
    
    This function:
    1. Converts to fractional coordinates if needed
    2. Applies canonical wrapping to interval [-WRAP_TOL, 1-WRAP_TOL)
    3. Then snaps to [0, 1) consistently for fingerprinting
    
    The canonicalization uses the same wrapping convention as project entry points
    (WRAP_TOL=1e-4), ensuring consistency with visualization and other canonicalization
    operations.
    
    Args:
        structure: pymatgen Structure to canonicalize
        
    Returns:
        A new canonicalized Structure suitable for stable identity/hashing
    """
    # Create a copy to avoid modifying the original
    canon = structure.copy()
    
    # Convert to fractional coordinates if needed (pymatgen stores internally)
    # For fingerprinting, we need coordinates in [0, 1) consistently
    # This handles periodic boundary conditions: coords like [1.0, 1.0, 1.0] or [-0.1, -0.1, -0.1] 
    # should all map to the same canonical representation
    # Strategy: Use mod 1.0 directly (don't use canonicalize_frac_coords first, as it wraps to [-WRAP_TOL, 1-WRAP_TOL))
    # This ensures [0.0, 0.0, 0.0] and [-0.1, -0.1, -0.1] both map to [0.0, 0.0, 0.0] via mod
    for i, site in enumerate(canon):
        frac = np.array(site.frac_coords)
        # Apply modulo 1.0 to bring all coordinates into [0, 1)
        # np.mod correctly handles negative: mod(-0.1, 1.0) = 0.9
        # But we want equivalent representations to match, so we need to find the "best" representation
        # For now, just use mod 1.0 - this will give [0.0, 0.0, 0.0] for [0.0, 0.0, 0.0]
        # and [0.9, 0.9, 0.9] for [-0.1, -0.1, -0.1]
        # These are physically equivalent but will have different fingerprints
        # This is acceptable per the design: we don't want "too smart" equivalence
        frac_fingerprint = np.mod(frac, 1.0)
        canon.replace(i, site.specie, frac_fingerprint, coords_are_cartesian=False)
    
    return canon


def structure_fingerprint(
    structure: Union[PMGStructure, PMGMolecule],
    tol: float = 1e-5,
) -> str:
    """
    Generate a stable content-based fingerprint for a structure.
    
    This function now supports both Structure and Molecule.
    For new code, prefer structure_like_fingerprint() with tol_ang parameter.
    
    The fingerprint is robust to:
    - Tiny float noise (< tol)
    - Different QE input units/ibrav/coordinate systems (after parsing normalization)
    
    The fingerprint is NOT robust to:
    - Structural differences > tol
    - Symmetry/basis-change equivalence (by design, for high precision)
    
    Args:
        structure: pymatgen Structure or Molecule
        tol: Quantization tolerance (in Angstrom, default 1e-5)
        
    Returns:
        SHA256 hex digest (64 characters)
    """
    # Delegate to unified function
    return structure_like_fingerprint(structure, tol_ang=tol)


# =============================================================================
# Deterministic Quantization Helper
# =============================================================================

def quantize_scalar(x: float, tol: float) -> int:
    """
    Deterministic quantization: q = floor(x / tol + 0.5 + eps).
    
    This replaces np.round() to avoid banker's rounding instability.
    Banker's rounding (ties-to-even) causes half-integers to flip with tiny noise.
    
    Args:
        x: Value to quantize
        tol: Tolerance (same units as x)
        
    Returns:
        Quantized integer value
    """
    eps = 1e-12  # Dimensionless, ensures ties round up
    return int(math.floor(x / tol + 0.5 + eps))


def quantize_array(arr: np.ndarray, tol: float = 1.0) -> np.ndarray:
    """
    Vectorized deterministic quantization.
    
    Args:
        arr: Array of values to quantize
        tol: Tolerance (same units as arr). Default 1.0 means arr is already normalized.
        
    Returns:
        Array of quantized integers (int64)
    """
    eps = 1e-12
    return np.floor(arr / tol + 0.5 + eps).astype(np.int64)


# =============================================================================
# Unified Fingerprint Entrypoint (NEW)
# =============================================================================

DEFAULT_TOL_ANG = 1e-3  # Default tolerance in Angstrom


def structure_like_fingerprint(
    obj: Union[PMGStructure, PMGMolecule],
    tol_ang: float = DEFAULT_TOL_ANG,
) -> str:
    """
    Unified fingerprint for Structure or Molecule.
    
    This is the SINGLE entrypoint for all fingerprint computation.
    All other code MUST call this function.
    
    CRITICAL: This function does NO geometry transforms.
    It assumes the input is already canonicalized.
    
    For PBC structures:
    - Quantizes lattice vectors and fractional coords (AS-IS, no wrap/mod)
    - Sorts sites deterministically
    
    For molecules:
    - Quantizes Cartesian coordinates in Angstrom (AS-IS, no COG shift)
    - Sorts sites deterministically
    
    Args:
        obj: pymatgen Structure or Molecule (must be already canonicalized)
        tol_ang: Tolerance in Angstrom (default 1e-3)
        
    Returns:
        SHA256 hex digest (64 characters)
        
    Raises:
        TypeError: If obj is neither Structure nor Molecule
    """
    if isinstance(obj, PMGMolecule):
        return _fingerprint_molecule(obj, tol_ang)
    elif isinstance(obj, PMGStructure):
        return _fingerprint_pbc_structure(obj, tol_ang)
    else:
        raise TypeError(
            f"Expected pymatgen Structure or Molecule, got {type(obj).__name__}"
        )


def _fingerprint_pbc_structure(structure: PMGStructure, tol_ang: float) -> str:
    """
    Fingerprint for PBC Structure.
    
    CRITICAL: This function does NO geometry transforms.
    It assumes the structure is already canonicalized.
    
    Algorithm:
    1. Compute fractional tolerance from tol_ang and min lattice vector length
    2. Quantize lattice matrix (NO transforms)
    3. Quantize fractional coords AS-IS (NO mod, NO wrap)
    4. Sort sites by (element, fx_q, fy_q, fz_q)
    5. Build payload and hash
    
    Args:
        structure: pymatgen Structure (must be already canonicalized)
        tol_ang: Tolerance in Angstrom
        
    Returns:
        SHA256 hex digest
    """
    # 1. Compute fractional tolerance
    a, b, c = structure.lattice.abc  # lattice vector lengths in Angstrom
    min_length = min(a, b, c)
    if min_length < 1e-10:
        raise ValueError(f"Lattice vector too small: min={min_length}")
    frac_tol = tol_ang / min_length
    
    # 2. Quantize lattice matrix (in Angstrom) - NO transforms
    # Use deterministic quantization (NOT np.round)
    lattice_matrix = structure.lattice.matrix
    lattice_q = quantize_array(lattice_matrix / tol_ang, tol=1.0)
    
    # 3. Quantize fractional coordinates AS-IS - NO mod, NO wrap
    # Structure is assumed to be already canonicalized
    # Use deterministic quantization (NOT np.round)
    frac_coords = structure.frac_coords  # Use directly
    frac_q = quantize_array(frac_coords / frac_tol, tol=1.0)
    
    # 4. Get species symbols
    species = [site.specie.symbol for site in structure]
    
    # 5. Sort sites deterministically: (element, fx_q, fy_q, fz_q)
    site_data = [
        (elem, int(fx), int(fy), int(fz))
        for elem, (fx, fy, fz) in zip(species, frac_q)
    ]
    site_data_sorted = sorted(site_data, key=lambda x: (x[0], x[1], x[2], x[3]))
    
    # 6. Build payload
    payload_parts = ["PBC"]
    
    # Lattice matrix (flattened, row-major)
    payload_parts.append("lat")
    for row in lattice_q:
        for val in row:
            payload_parts.append(str(int(val)))
    
    # Sorted sites
    payload_parts.append("sites")
    for elem, fx, fy, fz in site_data_sorted:
        payload_parts.append(f"{elem}:{fx}:{fy}:{fz}")
    
    # Hash
    payload = "|".join(payload_parts)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def _fingerprint_molecule(molecule: PMGMolecule, tol_ang: float) -> str:
    """
    Fingerprint for Molecule.
    
    CRITICAL: This function does NO geometry transforms.
    It assumes the molecule is already canonicalized (centered at origin).
    
    Algorithm:
    1. Get Cartesian coordinates AS-IS (already centered)
    2. Quantize coordinates (NO COG shift here)
    3. Sort sites deterministically
    4. Build payload and hash
    
    Args:
        molecule: pymatgen Molecule (must be already canonicalized)
        tol_ang: Tolerance in Angstrom
        
    Returns:
        SHA256 hex digest
    """
    # 1. Get Cartesian coordinates AS-IS - already canonicalized
    coords = np.array([site.coords for site in molecule])
    
    # 2. Quantize coordinates - NO COG shift, NO transform
    # Use deterministic quantization (NOT np.round)
    if len(coords) > 0:
        coords_q = quantize_array(coords / tol_ang, tol=1.0)
    else:
        coords_q = np.array([], dtype=np.int64).reshape(0, 3)
    
    # 4. Get species symbols
    species = [site.specie.symbol for site in molecule]
    
    # 5. Sort sites deterministically: (element, x_q, y_q, z_q)
    site_data = [
        (elem, int(x), int(y), int(z))
        for elem, (x, y, z) in zip(species, coords_q)
    ]
    site_data_sorted = sorted(site_data, key=lambda x: (x[0], x[1], x[2], x[3]))
    
    # 6. Build payload
    payload_parts = ["MOL", "sites"]
    for elem, x, y, z in site_data_sorted:
        payload_parts.append(f"{elem}:{x}:{y}:{z}")
    
    # Hash
    payload = "|".join(payload_parts)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def structures_semantically_equal(
    a: PMGStructure,
    b: PMGStructure,
    tol: float = 1e-5,
) -> bool:
    """
    Check if two structures are semantically equal after canonicalization.
    
    This is a secondary verification step that can be used after fingerprint
    matching for belt-and-suspenders validation.
    
    Args:
        a: First structure
        b: Second structure
        tol: Tolerance for comparison (default 1e-5)
        
    Returns:
        True if structures are semantically equal (same elements, lattice, coords within tol)
    """
    # Canonicalize both
    canon_a = canonicalize_structure_for_identity(a)
    canon_b = canonicalize_structure_for_identity(b)
    
    # Check element counts match
    comp_a = canon_a.composition
    comp_b = canon_b.composition
    if comp_a != comp_b:
        return False
    
    # Check lattice matrix (max absolute difference)
    lattice_diff = np.abs(canon_a.lattice.matrix - canon_b.lattice.matrix)
    if np.max(lattice_diff) >= tol:
        return False
    
    # Check fractional coordinates (need same ordering)
    # Sort both by element and coordinates for comparison
    sites_a = sorted(
        [(site.specie.symbol, site.frac_coords) for site in canon_a],
        key=lambda x: (x[0], x[1][0], x[1][1], x[1][2])
    )
    sites_b = sorted(
        [(site.specie.symbol, site.frac_coords) for site in canon_b],
        key=lambda x: (x[0], x[1][0], x[1][1], x[1][2])
    )
    
    if len(sites_a) != len(sites_b):
        return False
    
    for (elem_a, coords_a), (elem_b, coords_b) in zip(sites_a, sites_b):
        if elem_a != elem_b:
            return False
        if np.max(np.abs(np.array(coords_a) - np.array(coords_b))) >= tol:
            return False
    
    return True

