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


class SpinOption(str, Enum):
    """
    Spin treatment options.
    
    Physical meaning:
    - NONSPIN: Closed-shell systems, non-magnetic (nspin=1)
    - COLLINEAR: Spin-polarized with magnetization along z (nspin=2)
    - NONCOLLINEAR: Full vector magnetization (noncolin=.true.)
    """
    NONSPIN = "nonspin"
    COLLINEAR = "collinear"
    NONCOLLINEAR = "noncollinear"


class SOCOption(str, Enum):
    """
    Spin-orbit coupling options.
    
    Physical meaning:
    - NO_SOC: No relativistic spin-orbit interaction
    - WITH_SOC: Include spin-orbit coupling (requires noncollinear + FR pseudos)
    
    Note: WITH_SOC requires SpinOption.NONCOLLINEAR per physics constraints.
    """
    NO_SOC = "no_soc"
    WITH_SOC = "with_soc"


class MaterialOption(str, Enum):
    """
    Material type options (electronic structure characteristics).
    
    Physical meaning:
    - INSULATOR: Systems with a band gap, fixed occupations or tetrahedra
    - METAL: Conducting systems, requires smearing for fractional occupations
    
    This affects how Fermi level / occupations are handled.
    """
    INSULATOR = "insulator"
    METAL = "metal"


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
DIMENSION_SPIN: Final[str] = "spin"
DIMENSION_SOC: Final[str] = "soc"
DIMENSION_MATERIAL: Final[str] = "material"

# All v0 dimensions
V0_DIMENSIONS: Final[tuple[str, ...]] = (
    DIMENSION_SPIN,
    DIMENSION_SOC,
    DIMENSION_MATERIAL,
)

