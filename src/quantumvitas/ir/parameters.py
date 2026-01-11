"""
IR Parameter Registry.

Defines IR parameters as physics-driven, engine-agnostic quantities.

IR parameters MUST NOT contain qe_key or engine identifiers.
qe_key belongs to the IR↔QE adapter layer.
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class IRParameter:
    """
    IR parameter definition (engine-agnostic).
    
    IR parameters represent physical quantities only.
    They MUST NOT contain engine-specific references (qe_key, qe_section, etc.).
    """
    ir_key: str  # Canonical IR parameter name (e.g., "ecutwfc", "nspin", "conv_thr")
    physical_meaning: str  # Physical description (1-2 sentences)
    dimension: str  # Physical dimension: "Energy", "Length", "Dimensionless", "Bool", "Enum", "Integer", "Struct"
    ir_base_unit: Optional[str]  # IR base unit: "Ry", "Bohr", None
    type: str  # Python type: "float", "int", "bool", "str", "dict"
    comment: str  # Additional documentation (initially derived from QE metadata but IR-owned)


# IR Parameter Registry (v0: 18 parameters)
IR_REGISTRY: Dict[str, IRParameter] = {
    # Magnetism dimension (3 parameters)
    "nspin": IRParameter(
        ir_key="nspin",
        physical_meaning="Number of spin components for magnetization. 1=none, 2=collinear, 4=noncollinear.",
        dimension="Dimensionless",
        ir_base_unit=None,
        type="int",
        comment="Integer: 1 for nonmagnetic, 2 for collinear magnetism, 4 for noncollinear magnetism.",
    ),
    "noncolin": IRParameter(
        ir_key="noncolin",
        physical_meaning="Enable noncollinear magnetism (vector magnetization).",
        dimension="Bool",
        ir_base_unit=None,
        type="bool",
        comment="Boolean flag. When True, magnetization can point in any direction (noncollinear magnetism).",
    ),
    "lspinorb": IRParameter(
        ir_key="lspinorb",
        physical_meaning="Enable spin-orbit coupling (requires noncollinear magnetism).",
        dimension="Bool",
        ir_base_unit=None,
        type="bool",
        comment="Boolean flag. When True, includes spin-orbit coupling effects. Requires noncolin=True.",
    ),
    
    # OccupationsScheme dimension (3 parameters)
    "occupations": IRParameter(
        ir_key="occupations",
        physical_meaning="Occupation scheme for electronic states. Fixed occupations for insulators, smearing for metals.",
        dimension="Enum",
        ir_base_unit=None,
        type="str",
        comment="Enum: 'fixed' for insulators, 'smearing' for metals, 'tetrahedra' for tetrahedra method.",
    ),
    "smearing": IRParameter(
        ir_key="smearing",
        physical_meaning="Smearing type for metallic systems.",
        dimension="Enum",
        ir_base_unit=None,
        type="str",
        comment="Enum: 'gaussian', 'fermi', 'marzari-vanderbilt', etc. Used with occupations='smearing'.",
    ),
    "degauss": IRParameter(
        ir_key="degauss",
        physical_meaning="Smearing width for metallic systems.",
        dimension="Energy",
        ir_base_unit="Ry",
        type="float",
        comment="Energy parameter in Ry. Typical values: 0.01-0.05 Ry for metals.",
    ),
    
    # Precision dimension (4 parameters)
    "ecutwfc": IRParameter(
        ir_key="ecutwfc",
        physical_meaning="Kinetic energy cutoff for plane-wave expansion of wavefunctions. Determines basis set quality and computational cost.",
        dimension="Energy",
        ir_base_unit="Ry",
        type="float",
        comment="Energy parameter in Ry. Higher values improve accuracy but increase computational cost. Typical range: 20-100 Ry for norm-conserving pseudopotentials.",
    ),
    "ecutrho": IRParameter(
        ir_key="ecutrho",
        physical_meaning="Kinetic energy cutoff for plane-wave expansion of charge density.",
        dimension="Energy",
        ir_base_unit="Ry",
        type="float",
        comment="Energy parameter in Ry. Typically 4-8 times ecutwfc for norm-conserving pseudopotentials.",
    ),
    "conv_thr": IRParameter(
        ir_key="conv_thr",
        physical_meaning="SCF convergence threshold (energy change per electron).",
        dimension="Energy",
        ir_base_unit="Ry",
        type="float",
        comment="Energy parameter in Ry. Typical values: 1e-4 to 1e-6 Ry. Lower values = stricter convergence.",
    ),
    "K_POINTS": IRParameter(
        ir_key="K_POINTS",
        physical_meaning="K-point mesh for Brillouin Zone integration.",
        dimension="Struct",
        ir_base_unit=None,
        type="dict",
        comment="Structured card (not namelist). v0 canonicalization: gamma/automatic/crystal(list)/crystal_b(path endpoints + interpolation count).",
    ),
    
    # Convergence dimension (5 parameters)
    "mixing_beta": IRParameter(
        ir_key="mixing_beta",
        physical_meaning="SCF charge density mixing factor (0-1).",
        dimension="Dimensionless",
        ir_base_unit=None,
        type="float",
        comment="Dimensionless ratio (0-1). Higher values = more aggressive mixing, faster convergence but potentially unstable. Typical: 0.1-0.7.",
    ),
    "electron_maxstep": IRParameter(
        ir_key="electron_maxstep",
        physical_meaning="Maximum number of SCF iterations.",
        dimension="Dimensionless",
        ir_base_unit=None,
        type="int",
        comment="Integer. Maximum iterations before SCF is considered failed. Typical: 100-250.",
    ),
    "mixing_mode": IRParameter(
        ir_key="mixing_mode",
        physical_meaning="SCF charge density mixing algorithm.",
        dimension="Enum",
        ir_base_unit=None,
        type="str",
        comment="Enum: 'plain' (simple mixing), 'TF' (Thomas-Fermi), 'local-TF' (local Thomas-Fermi).",
    ),
    "mixing_ndim": IRParameter(
        ir_key="mixing_ndim",
        physical_meaning="Number of previous iterations used in charge density mixing scheme.",
        dimension="Dimensionless",
        ir_base_unit=None,
        type="int",
        comment="Integer. Number of previous charge densities to keep for mixing. Typical: 8-12.",
    ),
    "diagonalization": IRParameter(
        ir_key="diagonalization",
        physical_meaning="Diagonalization method for solving the Kohn-Sham equations.",
        dimension="Enum",
        ir_base_unit=None,
        type="str",
        comment="Enum: 'david' (Davidson), 'cg' (conjugate gradient), 'rmm-davidson' (residual minimization).",
    ),
    
    # Low-hanging additions (3 parameters)
    "nbnd": IRParameter(
        ir_key="nbnd",
        physical_meaning="Number of electronic states (bands) to be calculated.",
        dimension="Dimensionless",
        ir_base_unit=None,
        type="int",
        comment="Integer. For insulators: number of valence bands (nbnd = # of electrons / 2). For metals: typically 20% more (minimum 4 more).",
    ),
    "nosym": IRParameter(
        ir_key="nosym",
        physical_meaning="Disable use of crystal symmetry.",
        dimension="Bool",
        ir_base_unit=None,
        type="bool",
        comment="Boolean flag. When True, symmetry is not used. Consequences: k-point list used as-is, charge density not symmetrized.",
    ),
    "noinv": IRParameter(
        ir_key="noinv",
        physical_meaning="Disable time-reversal symmetry.",
        dimension="Bool",
        ir_base_unit=None,
        type="bool",
        comment="Boolean flag. When True, time-reversal symmetry is not used. k and -k are treated as distinct.",
    ),
}


def validate_ir_registry() -> None:
    """
    Validate IR registry.
    
    Raises:
        ValueError: If registry is invalid
    """
    if not IR_REGISTRY:
        raise ValueError("IR_REGISTRY is empty")
    
    for ir_key, param in IR_REGISTRY.items():
        if param.ir_key != ir_key:
            raise ValueError(f"Mismatch: registry key '{ir_key}' != parameter ir_key '{param.ir_key}'")
        
        if not param.physical_meaning:
            raise ValueError(f"IR parameter '{ir_key}' missing physical_meaning")
        
        if param.dimension not in ("Energy", "Length", "Dimensionless", "Bool", "Enum", "Integer", "Struct"):
            raise ValueError(f"IR parameter '{ir_key}' has invalid dimension: {param.dimension}")
        
        if param.dimension in ("Energy", "Length") and not param.ir_base_unit:
            raise ValueError(f"IR parameter '{ir_key}' has dimension '{param.dimension}' but missing ir_base_unit")
        
        if param.type not in ("float", "int", "bool", "str", "dict"):
            raise ValueError(f"IR parameter '{ir_key}' has invalid type: {param.type}")


def get_ir_parameter(ir_key: str) -> Optional[IRParameter]:
    """Get IR parameter by key."""
    return IR_REGISTRY.get(ir_key)


def list_ir_parameters() -> list[str]:
    """List all IR parameter keys."""
    return sorted(IR_REGISTRY.keys())


# Validate registry on import
validate_ir_registry()

