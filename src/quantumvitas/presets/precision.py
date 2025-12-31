"""
Precision preset advisor and computation.

This module provides:
- PrecisionAdvisor: Computes precision-dependent parameters from structure + pseudos
- Cutoff calculation from PSEUDO_FILE_INDEX.json
- K-mesh calculation from lattice vectors using reciprocal space formulation

Per Constitution: These are runtime-only computations, never persisted.
"""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import math

from quantumvitas.presets.dimensions import PrecisionOption


# ============================================================================
# Centralized Precision Constants
# ============================================================================

@dataclass(frozen=True)
class PrecisionLevelConstants:
    """
    Centralized constants for a precision level.
    
    All precision-related parameters are defined here for consistency.
    """
    # K-point spacing in reciprocal space (Å⁻¹)
    # nk_i = max(1, ceil(|b_i| / delta_k))
    delta_k: float
    
    # SCF convergence threshold
    conv_thr: float
    
    # Cutoff multiplier (applied to recommended pseudo cutoffs)
    # Symmetric: 0.8 / 1.0 / 1.2
    cutoff_multiplier: float


# Canonical precision constants (centralized configuration)
PRECISION_CONSTANTS: Dict[PrecisionOption, PrecisionLevelConstants] = {
    PrecisionOption.LOW: PrecisionLevelConstants(
        delta_k=0.30,  # Coarse k-spacing
        conv_thr=1e-6,
        cutoff_multiplier=0.8,  # Symmetric: 1.0 - 0.2
    ),
    PrecisionOption.MED: PrecisionLevelConstants(
        delta_k=0.20,  # Standard k-spacing
        conv_thr=1e-8,
        cutoff_multiplier=1.0,  # Baseline
    ),
    PrecisionOption.HIGH: PrecisionLevelConstants(
        delta_k=0.15,  # Fine k-spacing
        conv_thr=1e-10,
        cutoff_multiplier=1.2,  # Symmetric: 1.0 + 0.2
    ),
}

# Tolerance for conv_thr comparison in detection
CONV_THR_ABS_TOL = 1e-11

# Default cutoffs when pseudo data is unavailable
DEFAULT_ECUTWFC = 50.0  # Ry
DEFAULT_ECUTRHO = 400.0  # Ry (8× ecutwfc for USPP/PAW)

# NSCF uses denser k-mesh than SCF by this factor
# nk_i(nscf) = max(1, nk_i(scf) * NSCF_KMESH_FACTOR)
NSCF_KMESH_FACTOR = 2


# Legacy alias for backward compatibility
@dataclass(frozen=True)
class PrecisionConfig:
    """Legacy configuration class - use PRECISION_CONSTANTS instead."""
    k_density: float  # Deprecated: use delta_k
    conv_thr: float
    cutoff_multiplier: float


# Legacy mapping (for tests that may still use it)
PRECISION_CONFIGS: Dict[PrecisionOption, PrecisionConfig] = {
    level: PrecisionConfig(
        k_density=2 * math.pi / const.delta_k,  # Approximate conversion
        conv_thr=const.conv_thr,
        cutoff_multiplier=const.cutoff_multiplier,
    )
    for level, const in PRECISION_CONSTANTS.items()
}


# ============================================================================
# K-Mesh Calculation (Reciprocal Space Formulation)
# ============================================================================

def compute_reciprocal_lengths(lattice_matrix: List[List[float]]) -> Tuple[float, float, float]:
    """
    Compute reciprocal lattice vector lengths |b_i| from real-space lattice.
    
    For a general lattice, b_i = 2π * (a_j × a_k) / V where V is the cell volume.
    For each direction, |b_i| gives the spacing in reciprocal space.
    
    Args:
        lattice_matrix: 3x3 lattice vectors in Angstrom (row vectors a1, a2, a3)
        
    Returns:
        Tuple of (|b1|, |b2|, |b3|) in Å⁻¹
    """
    a1 = lattice_matrix[0]
    a2 = lattice_matrix[1]
    a3 = lattice_matrix[2]
    
    # Cross products
    def cross(u, v):
        return [
            u[1] * v[2] - u[2] * v[1],
            u[2] * v[0] - u[0] * v[2],
            u[0] * v[1] - u[1] * v[0],
        ]
    
    def dot(u, v):
        return sum(ui * vi for ui, vi in zip(u, v))
    
    def norm(v):
        return math.sqrt(sum(x**2 for x in v))
    
    # Volume = a1 · (a2 × a3)
    a2_cross_a3 = cross(a2, a3)
    volume = abs(dot(a1, a2_cross_a3))
    
    if volume < 1e-10:
        # Degenerate cell - return safe defaults
        return (1.0, 1.0, 1.0)
    
    # Reciprocal vectors: b_i = 2π * (a_j × a_k) / V
    b1 = [2 * math.pi * x / volume for x in a2_cross_a3]
    
    a3_cross_a1 = cross(a3, a1)
    b2 = [2 * math.pi * x / volume for x in a3_cross_a1]
    
    a1_cross_a2 = cross(a1, a2)
    b3 = [2 * math.pi * x / volume for x in a1_cross_a2]
    
    return (norm(b1), norm(b2), norm(b3))


def compute_kmesh(
    lattice_matrix: List[List[float]],
    delta_k: float,
) -> Tuple[int, int, int, int, int, int]:
    """
    Compute k-point mesh from lattice vectors using reciprocal space formulation.
    
    Formula: nk_i = max(1, ceil(|b_i| / Δk))
    where |b_i| is the length of reciprocal lattice vector i in Å⁻¹.
    
    No slab/vacuum heuristics - this is the physics-correct approach.
    
    Args:
        lattice_matrix: 3x3 lattice vectors in Angstrom (row vectors)
        delta_k: k-point spacing in Å⁻¹ (smaller = denser mesh)
        
    Returns:
        Tuple of (nk1, nk2, nk3, sk1, sk2, sk3) where sk are shifts (always 0)
        
    Example for Si (a ≈ 5.43 Å, |b| ≈ 1.157 Å⁻¹):
        - delta_k=0.30: nk = ceil(1.157/0.30) = 4
        - delta_k=0.20: nk = ceil(1.157/0.20) = 6
        - delta_k=0.15: nk = ceil(1.157/0.15) = 8
    """
    # Compute reciprocal lattice vector lengths
    b1_len, b2_len, b3_len = compute_reciprocal_lengths(lattice_matrix)
    
    # Compute nk for each direction: nk = ceil(|b| / Δk)
    nk1 = max(1, math.ceil(b1_len / delta_k))
    nk2 = max(1, math.ceil(b2_len / delta_k))
    nk3 = max(1, math.ceil(b3_len / delta_k))
    
    # Shifts: always 0 0 0 (Gamma-centered)
    return (nk1, nk2, nk3, 0, 0, 0)


def compute_kmesh_from_structure(
    structure: Any,  # pymatgen Structure
    delta_k: float,
) -> Tuple[int, int, int, int, int, int]:
    """
    Compute k-mesh from a pymatgen Structure object.
    
    Args:
        structure: pymatgen Structure with lattice
        delta_k: k-point spacing in Å⁻¹
        
    Returns:
        Tuple of (nk1, nk2, nk3, sk1, sk2, sk3)
    """
    lattice_matrix = [list(vec) for vec in structure.lattice.matrix]
    return compute_kmesh(lattice_matrix, delta_k)


# ============================================================================
# PSEUDO_FILE_INDEX Caching
# ============================================================================

@lru_cache(maxsize=1)
def _load_pseudo_index_cached(repo_root_str: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Load PSEUDO_FILE_INDEX.json with caching.
    
    Uses lru_cache to ensure the index is loaded only once per process.
    
    Args:
        repo_root_str: String path to repo root (hashable for cache key)
        
    Returns:
        List of file entries from PSEUDO_FILE_INDEX.json
    """
    try:
        from quantumvitas.core.pseudo_libinfo import load_pseudo_libinfo_bundle
        repo_root = Path(repo_root_str) if repo_root_str else None
        bundle = load_pseudo_libinfo_bundle(repo_root)
        return bundle.index.get("files", [])
    except Exception:
        # If index loading fails, return empty list
        return []


def get_pseudo_index(repo_root: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    Get the cached PSEUDO_FILE_INDEX files list.
    
    Args:
        repo_root: Optional repo root path
        
    Returns:
        List of file entries (cached)
    """
    repo_root_str = str(repo_root) if repo_root else None
    return _load_pseudo_index_cached(repo_root_str)


def clear_pseudo_index_cache():
    """Clear the PSEUDO_FILE_INDEX cache (for testing)."""
    _load_pseudo_index_cached.cache_clear()


# ============================================================================
# Cutoff Calculation from PSEUDO_FILE_INDEX
# ============================================================================

def get_cutoffs_from_index(
    sha256: str,
    index_files: List[Dict[str, Any]],
) -> Tuple[Optional[float], Optional[float]]:
    """
    Look up recommended cutoffs from PSEUDO_FILE_INDEX by sha256.
    
    Args:
        sha256: SHA256 hash of the pseudopotential file
        index_files: List of file entries from PSEUDO_FILE_INDEX.json
        
    Returns:
        Tuple of (ecutwfc, ecutrho) in Ry. Either can be None if not available.
    """
    for entry in index_files:
        if entry.get("sha256") == sha256:
            ecutwfc = entry.get("cutoff_wfc_normal")
            ecutrho = entry.get("cutoff_rho_normal")
            
            # Handle "na" values
            if ecutwfc == "na" or ecutwfc is None:
                ecutwfc = None
            if ecutrho == "na" or ecutrho is None:
                ecutrho = None
            
            return (ecutwfc, ecutrho)
    
    return (None, None)


def get_cutoffs_from_index_by_sha_family(
    sha_family: str,
    index_files: List[Dict[str, Any]],
) -> Tuple[Optional[float], Optional[float]]:
    """
    Look up recommended cutoffs from PSEUDO_FILE_INDEX by sha_family.
    
    Uses sha_family for physical equivalence matching when exact sha256
    is not available.
    
    Args:
        sha_family: SHA family hash for physical equivalence
        index_files: List of file entries from PSEUDO_FILE_INDEX.json
        
    Returns:
        Tuple of (ecutwfc, ecutrho) in Ry. Either can be None if not available.
    """
    for entry in index_files:
        if entry.get("sha_family") == sha_family:
            ecutwfc = entry.get("cutoff_wfc_normal")
            ecutrho = entry.get("cutoff_rho_normal")
            
            # Handle "na" values
            if ecutwfc == "na" or ecutwfc is None:
                ecutwfc = None
            if ecutrho == "na" or ecutrho is None:
                ecutrho = None
            
            return (ecutwfc, ecutrho)
    
    return (None, None)


def aggregate_cutoffs(
    species_map: Dict[str, Dict[str, Any]],
    index_files: List[Dict[str, Any]],
) -> Tuple[float, float]:
    """
    Aggregate cutoffs across all species in a calculation.
    
    Takes the maximum recommended cutoff across all species.
    
    Args:
        species_map: Species mapping from calculation (element -> {pseudo_sha256, ...})
        index_files: List of file entries from PSEUDO_FILE_INDEX.json
        
    Returns:
        Tuple of (ecutwfc, ecutrho) in Ry.
        Uses defaults if no recommendations found.
    """
    max_ecutwfc = None
    max_ecutrho = None
    
    for element, entry in species_map.items():
        if not isinstance(entry, dict):
            continue
        
        sha256 = entry.get("pseudo_sha256")
        sha_family = entry.get("pseudo_sha_family")
        
        ecutwfc, ecutrho = None, None
        
        # Try sha256 first (exact match)
        if sha256:
            ecutwfc, ecutrho = get_cutoffs_from_index(sha256, index_files)
        
        # Fall back to sha_family if no match
        if ecutwfc is None and sha_family:
            ecutwfc, ecutrho = get_cutoffs_from_index_by_sha_family(sha_family, index_files)
        
        # Update maximums
        if ecutwfc is not None:
            max_ecutwfc = max(max_ecutwfc or 0, ecutwfc)
        if ecutrho is not None:
            max_ecutrho = max(max_ecutrho or 0, ecutrho)
    
    # Apply defaults if nothing found
    final_ecutwfc = max_ecutwfc if max_ecutwfc is not None else DEFAULT_ECUTWFC
    final_ecutrho = max_ecutrho if max_ecutrho is not None else DEFAULT_ECUTRHO
    
    # For NC pseudos, ecutrho is often not specified; use 4× ecutwfc
    # For USPP/PAW, ecutrho is typically 8-12× ecutwfc
    if final_ecutrho < 4 * final_ecutwfc:
        final_ecutrho = 4 * final_ecutwfc
    
    return (final_ecutwfc, final_ecutrho)


def round_cutoff_integer(value: float) -> int:
    """
    Round a cutoff to the nearest integer Ry.
    
    This ensures stable comparisons in detection.
    """
    return int(round(value))


# Legacy function for backward compatibility
def round_cutoff(value: float, step: float) -> float:
    """Deprecated: Use round_cutoff_integer instead."""
    return round(value / step) * step


# ============================================================================
# PrecisionAdvisor - Main Interface
# ============================================================================

@dataclass
class PrecisionAdvice:
    """
    Result of precision advisor computation.
    
    Contains all precision-dependent parameters ready for compilation.
    All cutoffs are integer Ry for stable comparison.
    """
    precision: PrecisionOption
    
    # K-points
    nk1: int
    nk2: int
    nk3: int
    sk1: int
    sk2: int
    sk3: int
    
    # Cutoffs (integer Ry)
    ecutwfc: int
    ecutrho: int
    
    # Convergence
    conv_thr: float
    
    # Metadata
    base_ecutwfc: Optional[float] = None  # Before multiplier
    base_ecutrho: Optional[float] = None  # Before multiplier
    delta_k: Optional[float] = None  # K-point spacing used
    reciprocal_lengths: Optional[Tuple[float, float, float]] = None


class PrecisionAdvisor:
    """
    Advisor for computing precision-dependent parameters.
    
    Combines structure information with pseudo library metadata
    to compute recommended K-mesh, cutoffs, and conv_thr for
    a given precision level.
    
    Usage:
        advisor = PrecisionAdvisor(species_map, structure)
        advice = advisor.advise(PrecisionOption.MED)
        # Use advice.ecutwfc, advice.nk1, etc.
    """
    
    def __init__(
        self,
        species_map: Dict[str, Dict[str, Any]],
        structure: Optional[Any] = None,  # pymatgen Structure
        lattice_matrix: Optional[List[List[float]]] = None,
        repo_root: Optional[Path] = None,
    ):
        """
        Initialize the advisor.
        
        Args:
            species_map: Species mapping from calculation
            structure: Optional pymatgen Structure (for lattice)
            lattice_matrix: Optional 3x3 lattice matrix (alternative to structure)
            repo_root: Optional repo root for loading PSEUDO_FILE_INDEX
        """
        self.species_map = species_map
        self.structure = structure
        self.repo_root = repo_root
        
        # Get lattice matrix
        if lattice_matrix is not None:
            self._lattice_matrix = lattice_matrix
        elif structure is not None:
            self._lattice_matrix = [list(vec) for vec in structure.lattice.matrix]
        else:
            # Default to 10 Å cubic cell if no structure provided
            self._lattice_matrix = [[10.0, 0, 0], [0, 10.0, 0], [0, 0, 10.0]]
    
    def advise(
        self,
        precision: PrecisionOption,
    ) -> PrecisionAdvice:
        """
        Compute precision advice for the given level.
        
        Args:
            precision: Desired precision level
            
        Returns:
            PrecisionAdvice with computed parameters
        """
        constants = PRECISION_CONSTANTS[precision]
        
        # Load pseudo index (cached)
        index_files = get_pseudo_index(self.repo_root)
        
        # Compute base cutoffs from pseudos
        base_ecutwfc, base_ecutrho = aggregate_cutoffs(self.species_map, index_files)
        
        # Apply precision multiplier and round to integer
        ecutwfc = round_cutoff_integer(base_ecutwfc * constants.cutoff_multiplier)
        ecutrho = round_cutoff_integer(base_ecutrho * constants.cutoff_multiplier)
        
        # Compute k-mesh using reciprocal space formulation
        nk1, nk2, nk3, sk1, sk2, sk3 = compute_kmesh(
            self._lattice_matrix, 
            constants.delta_k,
        )
        
        # Compute reciprocal lengths for metadata
        recip_lengths = compute_reciprocal_lengths(self._lattice_matrix)
        
        return PrecisionAdvice(
            precision=precision,
            nk1=nk1,
            nk2=nk2,
            nk3=nk3,
            sk1=sk1,
            sk2=sk2,
            sk3=sk3,
            ecutwfc=ecutwfc,
            ecutrho=ecutrho,
            conv_thr=constants.conv_thr,
            base_ecutwfc=base_ecutwfc,
            base_ecutrho=base_ecutrho,
            delta_k=constants.delta_k,
            reciprocal_lengths=recip_lengths,
        )
    
    def advise_all(self) -> Dict[PrecisionOption, PrecisionAdvice]:
        """
        Compute advice for all precision levels.
        
        Returns:
            Dict mapping PrecisionOption to PrecisionAdvice
        """
        return {
            level: self.advise(level)
            for level in PrecisionOption
        }
    
    def advise_for_step(
        self,
        precision: PrecisionOption,
        step_type: str,
    ) -> PrecisionAdvice:
        """
        Compute precision advice adjusted for a specific step type.
        
        Uses PrecisionReceiverSpec to determine step-type-specific adjustments:
        - nscf: K-mesh multiplied by NSCF_KMESH_FACTOR (2x denser)
        - bands_pw: Returns base advice (K_POINTS filtering done in integration)
        - scf/relax/etc: Standard advice
        
        Args:
            precision: Desired precision level
            step_type: Step type string (e.g., "scf", "nscf", "bands_pw")
            
        Returns:
            PrecisionAdvice adjusted for step type
        """
        from quantumvitas.presets.receivers import get_precision_receiver_spec
        
        # Get base advice
        advice = self.advise(precision)
        
        # Get receiver spec for step type
        spec = get_precision_receiver_spec(step_type)
        
        # Apply nscf mesh multiplier if needed
        if spec and spec.kmesh_strategy == "nscf":
            nk1 = max(1, advice.nk1 * NSCF_KMESH_FACTOR)
            nk2 = max(1, advice.nk2 * NSCF_KMESH_FACTOR)
            nk3 = max(1, advice.nk3 * NSCF_KMESH_FACTOR)
            
            return PrecisionAdvice(
                precision=advice.precision,
                nk1=nk1,
                nk2=nk2,
                nk3=nk3,
                sk1=advice.sk1,
                sk2=advice.sk2,
                sk3=advice.sk3,
                ecutwfc=advice.ecutwfc,
                ecutrho=advice.ecutrho,
                conv_thr=advice.conv_thr,
                base_ecutwfc=advice.base_ecutwfc,
                base_ecutrho=advice.base_ecutrho,
                delta_k=advice.delta_k,
                reciprocal_lengths=advice.reciprocal_lengths,
            )
        
        # For other steps (scf, bands_pw, etc.), return base advice
        # (bands_pw K_POINTS filtering is done in integration layer via receiver spec)
        return advice


# ============================================================================
# Utility Functions
# ============================================================================

def get_precision_advice(
    species_map: Dict[str, Dict[str, Any]],
    lattice_matrix: List[List[float]],
    precision: PrecisionOption,
    repo_root: Optional[Path] = None,
) -> PrecisionAdvice:
    """
    Convenience function to get precision advice.
    
    Args:
        species_map: Species mapping from calculation
        lattice_matrix: 3x3 lattice vectors in Angstrom
        precision: Desired precision level
        repo_root: Optional repo root
        
    Returns:
        PrecisionAdvice with computed parameters
    """
    advisor = PrecisionAdvisor(species_map, lattice_matrix=lattice_matrix, repo_root=repo_root)
    return advisor.advise(precision)


def get_canonical_precision_params(
    precision: PrecisionOption,
    lattice_matrix: List[List[float]],
    base_ecutwfc: float,
    base_ecutrho: float,
) -> Tuple[int, int, int, int, int, int, int, int, float]:
    """
    Get canonical precision parameters for a given level.
    
    This is used by the detector to compute expected values.
    
    Args:
        precision: Precision level
        lattice_matrix: 3x3 lattice vectors in Angstrom
        base_ecutwfc: Base ecutwfc from pseudos
        base_ecutrho: Base ecutrho from pseudos
        
    Returns:
        Tuple of (nk1, nk2, nk3, sk1, sk2, sk3, ecutwfc, ecutrho, conv_thr)
    """
    constants = PRECISION_CONSTANTS[precision]
    
    # K-mesh
    nk1, nk2, nk3, sk1, sk2, sk3 = compute_kmesh(lattice_matrix, constants.delta_k)
    
    # Cutoffs (integer)
    ecutwfc = round_cutoff_integer(base_ecutwfc * constants.cutoff_multiplier)
    ecutrho = round_cutoff_integer(base_ecutrho * constants.cutoff_multiplier)
    
    return (nk1, nk2, nk3, sk1, sk2, sk3, ecutwfc, ecutrho, constants.conv_thr)
