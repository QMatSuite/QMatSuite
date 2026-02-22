"""
Preset dimension definitions for QMatSuite.

This module defines the v0 preset dimensions as value objects (enums).
These are runtime-only concepts that are never persisted per Constitution 10.2.1.

Dimension semantics are derived from physics, not from QE parameter names:
- Spin: electron spin treatment (none, collinear, noncollinear)
- SOC: spin-orbit coupling (off, on)
- Material: electronic structure type (insulator, metal)
"""

from enum import Enum
from typing import Final


class MagnetismOption(str, Enum):
    """
    Magnetism treatment options (merged spin + SOC).
    
    Physical meaning:
    - NONMAGNETIC: Closed-shell systems, non-magnetic (nspin=1, noncolin=false, lspinorb=false)
    - COLLINEAR_LSDA: Spin-polarized with magnetization along z (nspin=2, noncolin=false, lspinorb=false)
    - NONCOLLINEAR: Full vector magnetization (noncolin=true, lspinorb=false, nspin not written)
    - NONCOLLINEAR_SOC: Noncollinear with spin-orbit coupling (noncolin=true, lspinorb=true, nspin not written)
    
    Note: SOC requires noncollinear treatment per physics constraints.
    """
    NONMAGNETIC = "nonmagnetic"
    COLLINEAR_LSDA = "collinear_lsda"
    NONCOLLINEAR = "noncollinear"
    NONCOLLINEAR_SOC = "noncollinear_soc"


class OccupationsSchemeOption(str, Enum):
    """
    Occupations / BZ integration scheme options.
    
    Physical meaning:
    - FIXED: Fixed occupations (gapped / default QE behavior)
    - SMEARING_GAUSSIAN: Gaussian smearing (degauss=0.02 Ry) for metals
    - TETRAHEDRA: Tetrahedra method for BZ integration
    
    This affects how Fermi level / occupations are handled and may affect
    convergence and DOS calculations.
    """
    FIXED = "fixed"
    SMEARING_GAUSSIAN = "smearing_gaussian"
    TETRAHEDRA = "tetrahedra"


class PrecisionOption(str, Enum):
    """
    Precision level options for computational accuracy.
    
    Physical meaning:
    - LOW: Quick screening, coarse k-mesh, relaxed convergence
    - MED: Production quality, balanced accuracy/cost
    - HIGH: High accuracy for forces, phonons, fine energy differences
    
    This affects:
    - K_POINTS mesh density (nk1, nk2, nk3)
    - ecutwfc, ecutrho (plane-wave cutoffs)
    - conv_thr (SCF convergence threshold)
    """
    LOW = "low"
    MED = "med"
    HIGH = "high"


class ConvergenceOption(str, Enum):
    """
    Convergence strategy options for SCF iterations.
    
    Physical meaning:
    - FAST: Fast convergence with aggressive mixing (mixing_beta=0.7, maxstep=100)
    - NORMAL: Balanced convergence (mixing_beta=0.4, maxstep=150)
    - ROBUST: Robust convergence with advanced mixing (mixing_beta=0.2, maxstep=200)
    - VERY_ROBUST: Very robust convergence for difficult systems (mixing_beta=0.1, maxstep=250)
    
    This affects:
    - mixing_beta: Charge density mixing parameter
    - electron_maxstep: Maximum SCF iterations
    - mixing_mode: Mixing algorithm (plain, TF, local-TF)
    - mixing_ndim: Number of previous iterations for mixing
    - diagonalization: Diagonalization algorithm (david, rmm-davidson, cg)
    
    Note: conv_thr is NOT controlled by convergence preset (belongs to precision).
    """
    FAST = "fast"
    NORMAL = "normal"
    ROBUST = "robust"
    VERY_ROBUST = "very_robust"


class _CustomType:
    """
    Singleton marker for heterogeneous preset values across steps.
    
    Per Constitution 10.5.1:
    - If steps have different values for a dimension → Custom
    - No "Unknown" state exists
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __repr__(self) -> str:
        return "Custom"
    
    def __str__(self) -> str:
        return "Custom"
    
    def __eq__(self, other) -> bool:
        return isinstance(other, _CustomType)
    
    def __hash__(self) -> int:
        return hash("Custom")


# Singleton instance for Custom value
CUSTOM: Final[_CustomType] = _CustomType()


# Dimension names as constants for consistency
DIMENSION_MAGNETISM: Final[str] = "magnetism"
DIMENSION_OCCUPATIONS_SCHEME: Final[str] = "occupations_scheme"
DIMENSION_PRECISION: Final[str] = "precision"
DIMENSION_QC_PRECISION: Final[str] = "qc_precision"
DIMENSION_CONVERGENCE: Final[str] = "convergence"

# v0 dimensions (magnetism, occupations_scheme)
V0_DIMENSIONS: Final[tuple[str, ...]] = (
    DIMENSION_MAGNETISM,
    DIMENSION_OCCUPATIONS_SCHEME,
)

# v1 dimensions (v0 + precision)
V1_DIMENSIONS: Final[tuple[str, ...]] = (
    DIMENSION_MAGNETISM,
    DIMENSION_OCCUPATIONS_SCHEME,
    DIMENSION_PRECISION,
)

