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
from typing import TYPE_CHECKING, List, Tuple, Union

import numpy as np

if TYPE_CHECKING:
    from pymatgen.core import Structure as PMGStructure
    from pymatgen.core import Molecule as PMGMolecule


def _get_pymatgen_types():
    """Lazy-load pymatgen classes used for runtime isinstance checks."""
    from pymatgen.core import Structure as PMGStructure
    from pymatgen.core import Molecule as PMGMolecule

    return PMGStructure, PMGMolecule


def structure_fingerprint(
    structure: Union["PMGStructure", "PMGMolecule"],
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

# SSOT: Single source of truth for fingerprint tolerance
DEFAULT_FINGERPRINT_TOL_ANG = 1e-3  # Default tolerance in Angstrom


def structure_like_fingerprint(
    obj: Union["PMGStructure", "PMGMolecule"],
    tol_ang: float = DEFAULT_FINGERPRINT_TOL_ANG,
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
    PMGStructure, PMGMolecule = _get_pymatgen_types()

    if isinstance(obj, PMGMolecule):
        return _fingerprint_molecule(obj, tol_ang)
    elif isinstance(obj, PMGStructure):
        return _fingerprint_pbc_structure(obj, tol_ang)
    else:
        raise TypeError(
            f"Expected pymatgen Structure or Molecule, got {type(obj).__name__}"
        )


def _fingerprint_pbc_structure(structure: "PMGStructure", tol_ang: float) -> str:
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


def _fingerprint_molecule(molecule: "PMGMolecule", tol_ang: float) -> str:
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
