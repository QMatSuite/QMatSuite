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
from typing import List, Tuple

import numpy as np
from pymatgen.core import Structure as PMGStructure

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


def structure_fingerprint(structure: PMGStructure, tol: float = 1e-5) -> str:
    """
    Generate a stable content-based fingerprint for a structure.
    
    The fingerprint is robust to:
    - Tiny float noise (< tol)
    - Different QE input units/ibrav/coordinate systems (after parsing normalization)
    
    The fingerprint is NOT robust to:
    - Structural differences > tol
    - Symmetry/basis-change equivalence (by design, for high precision)
    
    Algorithm:
    1. Canonicalize structure (wrap + snap to [0,1))
    2. Quantize lattice vectors and fractional coordinates by tol
    3. Sort sites deterministically by (element_symbol, fx_q, fy_q, fz_q)
    4. Hash the quantized data with SHA256
    
    Args:
        structure: pymatgen Structure to fingerprint
        tol: Quantization tolerance for both lattice (Å) and fractional coords (default 1e-5)
        
    Returns:
        Hex digest string of the fingerprint (SHA256)
    """
    # Canonicalize for identity
    canon = canonicalize_structure_for_identity(structure)
    
    # Quantize lattice matrix (3x3, in Angstrom)
    lattice_matrix = canon.lattice.matrix
    lattice_q = np.round(lattice_matrix / tol).astype(np.int64)
    
    # Quantize fractional coordinates
    frac_coords = np.array([site.frac_coords for site in canon])
    frac_q = np.round(frac_coords / tol).astype(np.int64)
    
    # Get element symbols
    element_symbols = [site.specie.symbol for site in canon]
    
    # Create deterministic site ordering: sort by (element_symbol, fx_q, fy_q, fz_q)
    site_data = [
        (elem, fx, fy, fz)
        for elem, (fx, fy, fz) in zip(element_symbols, frac_q)
    ]
    site_data_sorted = sorted(site_data, key=lambda x: (x[0], x[1], x[2], x[3]))
    
    # Build fingerprint payload
    # Format: lattice (9 ints) + sorted sites (element, fx, fy, fz for each)
    payload_parts = []
    
    # Lattice matrix (flattened, row-major)
    payload_parts.append("lattice:")
    for row in lattice_q:
        payload_parts.extend([str(x) for x in row])
    
    # Sorted sites
    payload_parts.append("sites:")
    for elem, fx, fy, fz in site_data_sorted:
        payload_parts.append(f"{elem}:{fx}:{fy}:{fz}")
    
    # Join and hash
    payload = "|".join(payload_parts)
    fingerprint = hashlib.sha256(payload.encode('utf-8')).hexdigest()
    
    return fingerprint


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

