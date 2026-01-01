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

